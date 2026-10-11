# Quotio Homebrew tap

Install [Quotio](https://github.com/nguyenphutrong/quotio) with Homebrew:

```sh
brew tap rookieko/quotio
brew install --cask rookieko/quotio/quotio
```

Update an existing installation:

```sh
brew update
brew upgrade --cask rookieko/quotio/quotio
```

## Automatic cask updates

The **Update Quotio cask** GitHub Actions workflow checks the latest stable
upstream release every six hours (00:23, 06:23, 12:23, and 18:23 UTC).
For a changed release, it downloads the DMG and verifies its size and GitHub-provided SHA256
when available, and commits the version and checksum to `main` only when
they change. Drafts and prereleases are rejected, and versions never go
backwards. An incomplete release fails without modifying the cask; the next
scheduled run tries again.

The workflow uses the repository's built-in `GITHUB_TOKEN` with
`contents: write`; no personal access token or additional secret is needed.
GitHub Actions must be enabled and branch rules must allow the bot to push
to `main`. Scheduled runs may be delayed, and GitHub disables schedules in
public repositories after 60 days without repository activity. If disabled,
re-enable the workflow in the repository's Actions tab.

To check immediately, open **Actions → Update Quotio cask → Run workflow**.
The workflow also runs when its updater, tests, or workflow file changes on
`main`. This updates the tap definition; each Mac installs the new version
with the commands above.

For local development:

```sh
python3 -B -m unittest discover -s tests -v
python3 -B scripts/update_quotio.py
```
