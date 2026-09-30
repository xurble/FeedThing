import json
import subprocess

import pytest
from bs4 import BeautifulSoup
from django.urls import reverse
from feeds.models import Subscription

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("operation", ["rename", "move", "promote", "unsubscribe"])
def test_manage_mutation_refreshes_sidebar(
    client, user, other_user, make_source, make_subscription, operation
):
    client.force_login(user)
    folder = Subscription.objects.create(user=user, name="Old folder")
    target = Subscription.objects.create(user=user, name="Target folder")
    sub = make_subscription(
        source=make_source(),
        parent=None if operation == "rename" else folder,
        name="Original feed",
    )
    make_subscription(
        user_override=other_user,
        source=make_source(feed_url="https://example.com/private.xml"),
        name="Private subscription",
    )
    page = client.get(reverse("manage"))
    assert page.status_code == 200
    script = next(
        tag.string
        for tag in BeautifulSoup(page.content, "html.parser").find_all("script")
        if tag.string and "function refreshFeedList()" in tag.string
    )
    paths = {
        "rename": (f"/subscription/{sub.pk}/details/", {"subname": "Renamed feed"}),
        "move": (f"/subscription/{sub.pk}/addto/{target.pk}/", {}),
        "promote": (f"/subscription/{sub.pk}/promote/", {}),
        "unsubscribe": (f"/subscription/{sub.pk}/unsubscribe/", {}),
    }
    path, data = paths[operation]
    response = client.post(path, data)
    assert response.status_code == 200
    refreshed = client.get(reverse("subscriptionlist"))
    assert refreshed.status_code == 200
    body = refreshed.content.decode()
    assert "Private subscription" not in body
    sidebar = BeautifulSoup(body, "html.parser")
    if operation == "rename":
        assert sidebar.find(id=f"sa{sub.pk}").get_text() == "Renamed feed"
    else:
        assert sidebar.find(id=f"s{folder.pk}") is None
        assert bool(sidebar.find(id=f"s{sub.pk}")) == (operation == "promote")
    if operation == "move":
        details = client.get(f"/subscription/{target.pk}/details/")
        assert "Original feed" in details.content.decode()
    if operation == "unsubscribe":
        assert not Subscription.objects.filter(pk=sub.pk).exists()

    # Execute the rendered page's real mutation callbacks with controlled AJAX.
    # The DOM/AJAX boundary is stubbed; Django above exercises those exact routes.
    harness = r"""
const assert = require('node:assert/strict');
const vm = require('node:vm');
const input = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
let pendingPost, refreshes = 0, sidebar, dragBindings = 0;
function $(selector) {
    return {
        length: 1,
        ready() {},
        serializeObject() { return {subname: 'Renamed feed'}; },
        html(value) { if (selector === '#feeds') sidebar = value; return this; },
        fadeOut(callback) { if (callback) callback(); return this; },
        fadeIn() { return this; },
        draggable() { dragBindings++; return this; },
        droppable() { dragBindings++; return this; },
        removeClass() { return this; }
    };
}
$.fn = {};
$.post = (url, data, callback) => {
    pendingPost = {url, callback: typeof data === 'function' ? data : callback};
};
$.get = (url, callback) => {
    assert.equal(url, input.refreshUrl);
    refreshes++;
    callback(input.fragment);
};
const context = { $, jQuery: $, document: {}, bootbox: {
    confirm(options) { options.callback(true); }
}};
vm.createContext(context);
vm.runInContext(input.script, context);
context.details = () => {};
const operations = {
    rename: () => context.saveSubscription(input.sid),
    move: () => context.addToGroup(input.sid, input.gid),
    promote: () => context.removeFromGroup(input.sid),
    unsubscribe: () => context.unsub(input.sid)
};
operations[input.operation]();
assert.equal(pendingPost.url, input.mutationUrl);
assert.equal(refreshes, 0, 'Do not refresh before the mutation succeeds');
pendingPost.callback(input.response);
assert.equal(refreshes, 1, 'Successful mutation must refresh the sidebar');
assert.equal(sidebar, input.fragment);
assert.equal(dragBindings, 2, 'Restore drag/drop handlers after replacing the sidebar');
"""
    result = subprocess.run(
        ["node", "-e", harness],
        input=json.dumps(
            {
                "script": script,
                "operation": operation,
                "sid": sub.pk,
                "gid": target.pk,
                "mutationUrl": path,
                "refreshUrl": reverse("subscriptionlist"),
                "fragment": body,
                "response": response.content.decode(),
            }
        ),
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
