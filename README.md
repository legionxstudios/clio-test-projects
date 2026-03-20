# Sitemap Word Count Scraper

A Python CLI tool that crawls a sitemap, fetches each page, and counts target word usage separately for:

- headings (`h1` through `h6`)
- body text

It removes common navigation, header, and footer sections before counting so the results focus on main content rather than site chrome.

## Features

- Accepts a sitemap URL or sitemap index.
- Splits counts into headings vs. body text.
- Excludes common nav/footer/header regions before counting.
- Supports multiple filter styles:
  - `--word` for exact words or phrases
  - `--regex` for regex-based matching
  - `--any-words` for OR-style token matching
  - `--all-words` for AND-style presence checks
- Outputs either JSON or a readable table.
- Lets you add extra CSS exclusion classes when needed.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
# No external packages required.
```

## Usage

```bash
python src/scrape_word_counts.py "https://example.com/sitemap.xml" \
  --word pricing \
  --regex "seo|search engine optimization" \
  --any-words "ai,artificial intelligence" \
  --all-words "seo,visibility" \
  --output table
```

## How exclusion works

The tool removes common structural regions and class-based content chrome before extracting text:

- `nav`
- `header`
- `footer`
- `[role='navigation']`
- `.nav`
- `.navbar`
- `.menu`
- `.footer`
- `.site-footer`
- `.site-header`

You can add more exclusions with repeated `--exclude-class` arguments, for example:

```bash
python src/scrape_word_counts.py "https://example.com/sitemap.xml" \
  --word pricing \
  --exclude-class ".sidebar" \
  --exclude-class ".breadcrumb"
```

## Output shape

JSON output contains:

- `sitemap_url`
- `page_count`
- `patterns`
- `totals`
- `pages`

Each page includes the URL plus separate `headings` and `body` counts for every filter.

## Notes

- `--word` uses word-boundary matching, which works best for single words and simple phrases.
- `--all-words` returns `1` per section if all listed words are present, rather than a repeated frequency total.
- If you want custom logic like stemming or fuzzy matching, this CLI is structured so those modes can be added later.
