# Sitemap Word Count Scraper

This project now includes both:

- a CLI for scripted runs
- a browser-based UI for easier manual use

The tool crawls a sitemap, fetches each page, excludes common nav/header/footer chrome, and counts target word usage separately in headings and body text.

## What you can use

### Web UI

Start the UI locally:

```bash
python app.py
```

Then open: `http://localhost:7860`

In the UI you can:

- enter a sitemap URL
- add exact words or phrases
- add regex filters for wording variations
- add OR and AND filter groups
- add extra excluded classes such as `sidebar` or `breadcrumb`
- review totals, per-page counts, and raw JSON

### CLI

```bash
python src/scrape_word_counts.py "https://example.com/sitemap.xml" \
  --word pricing \
  --regex "seo|search engine optimization" \
  --any-words "ai,artificial intelligence" \
  --all-words "seo,visibility" \
  --output table
```

## Matching modes

- `--word`: exact word or phrase matching
- `--regex`: regex-based matching
- `--any-words`: comma-separated OR token groups
- `--all-words`: comma-separated AND presence groups

## Exclusions

The analyzer ignores these patterns by default before counting text:

- `nav`
- `header`
- `footer`
- `[role="navigation"]`
- `.nav`
- `.navbar`
- `.menu`
- `.footer`
- `.site-footer`
- `.site-header`

You can add more excluded classes in the UI or via the CLI.

## Free hosting option

The repo now includes a `Dockerfile` so you can host the UI for free on **Hugging Face Spaces** as a Docker Space.

### Suggested free deployment steps

1. Create a free Hugging Face account.
2. Create a new **Docker Space**.
3. Push this repository to that Space.
4. Hugging Face will build the `Dockerfile` and expose the app on port `7860`.

The app entry point is:

```bash
python app.py
```

## Notes

- No third-party Python packages are required.
- The UI runs on the standard library WSGI server, so it is easy to run locally and easy to containerize.
- If you want CSV export, authentication, or persistent saved reports, those can be added next.
