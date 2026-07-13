# Contributing to AI SQL Analyst

First off, thank you for taking the time to contribute! 🎉

We welcome contributions of all kinds: bug fixes, new features, documentation improvements, or UI polish.

## How to Contribute

### 1. Reporting Bugs
- Search existing issues to ensure the bug hasn't been reported yet.
- Open a new issue with a clear title and description, including steps to reproduce, expected behavior, and screenshots if applicable.

### 2. Suggesting Enhancements
- Open an issue explaining the proposed change, why it's useful, and how it fits into the scope of the project.

### 3. Pull Requests
- Fork the repository.
- Create a feature branch: `git checkout -b feature/my-amazing-feature`.
- Make your changes, keeping coding styles consistent.
- Add test coverage for any new features or bug fixes.
- Run the test suite: `pytest` (ensure all 53 tests pass!).
- Commit your changes with meaningful messages: `git commit -m "feat: add schema profiling heatmap"`.
- Push to your branch and open a Pull Request against the `main` branch.

## Development Setup

See the [Running Locally](README.md#running-locally) section in the README for environment details.
All SQL queries should be validated against standard sqlglot structures to preserve read-only constraints.
