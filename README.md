# Numerus Data

## Overview

This repository hosts data for [Numerus App](https://github.com/konverner/numerus-app)

## Repository Structure

```
numerus-data/
├── channels.csv     # Youtube channels for data sourcing
├── manifest.json       # The "Entry Point" file the app checks first
├── scripts/            # Useful scripts for data processing
└── v1/                 # API Versioning folder (future-proofing)
    ├── en.json         # English data
    ├── fr.json         # French data
    ├── de.json         # German data
    ├── ru.json         # Russian data
    └── es.json         # Spanish data
```

## Submit Data

To contribute new data or suggest changes, please open a Pull Request with the relevant modifications to the JSON files in the appropriate language folder:

1. Fork the repository.
2. Make your changes in a new branch: modify language files in the `v1/` directory.
3. In `manifest.json`, update version for modified languages and `last_updated` timestamp as well. 
4. Submit a Pull Request for review.

## Scripts

### Append Items

A script to append items from one JSON file to another, useful for merging new data into existing datasets.

Usage: 

```bash
python scripts/append_items.py --base_file <path_to_base_json> --append_file <path_to_append_json> [--output <output_path>] [--dry-run]
```

### Filter Items

A script to filter items in a JSON file based on specific regex criteria. 

Usage:

```bash
python scripts/filter_items.py --input <path_to_input_json> -c <regex_pattern_1> -c <regex_pattern_2>
```

It will remove items that match the regex patterns based on 'subs' field. The script outputs a filtered JSON file in the `output/{timestamp}` directory.