from allauth.account.forms import SignupForm
from django import forms


class FTSignupForm(SignupForm):
    name = forms.CharField(max_length=30, label='Your Name')

    def save(self, request):
        user = super(FTSignupForm, self).save(request)
        user.name = self.cleaned_data['name']
        user.salutation = self.cleaned_data['name']
        user.save()
        return user
