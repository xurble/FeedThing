# Agent Guidelines

These rules always apply. Follow them when editing or adding code.

## Code Style

- Place all Python imports at the top of the file. Never import modules inline within functions or methods.
- Group imports in this order (separate groups with blank lines): (1) standard library, (2) third-party, (3) local/project.
- Use f-strings for string formatting in preference to `%`.

## Testing

- When running Django tests, use the `--keep-db` flag (or `--reuse-db` where supported) to preserve the test database. Omit it only after schema changes (migrations) that need a fresh DB.
- When implementing new features, add unit tests in the same change. Do not add features without tests.

## Code Maintenance

- Remove unused imports when modifying a file. Keep only imports that are used.

## Code Quality

- Follow existing code patterns and style conventions found in the codebase.
- Use appropriate Django patterns and utilities already established in the project.
- Maintain consistency with the existing codebase structure.

## Before Finishing

- Run the linter on modified files and fix any new issues.
- Run relevant tests when you have changed behaviour (e.g. the test suite for the app you edited).

## Security

- Do not add or leave hardcoded secrets, API keys, or credentials. Use settings or environment variables.

## Analysis & Documentation

- When asked to analyse the code and make recommendations, store created reports in `/docs`.
- Do not create README or other documentation files unless the user explicitly asks for them.

## Version Control

- Only ever create branches, commit or push code when explicitly asked to do so.
