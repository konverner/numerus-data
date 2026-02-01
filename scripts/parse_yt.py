"""Cleaner Analyzer for extracting numeric mentions from YouTube transcripts.

This module provides an `Analyzer` class that queries the YouTube Data API
to get recent uploads from a channel and uses `youtube_transcript_api` to
fetch transcripts and extract mentions of numbers with surrounding context.

Features:
- Uses `requests.Session` for HTTP reuse.
- Compiles regexes once.
- Returns structured dicts instead of nested lists.

Getting a YouTube Data API key
--------------------------------
1. Open the Google Cloud Console: https://console.cloud.google.com/
2. Create or select a project.
3. Enable the "YouTube Data API v3" for the project (APIs & Services → Library).
4. Go to "APIs & Services → Credentials" and click "Create credentials → API key".
5. (Recommended) Restrict the API key to the YouTube Data API and to appropriate
    HTTP referrers or IP addresses to reduce risk.

Notes:
- For some operations or higher quotas you may need to set up billing or use OAuth 2.0
    credentials instead of a plain API key—see Google's guide for details.
- Official docs: https://developers.google.com/youtube/v3/getting-started

Usage:
- Pass the API key to the script with `--key YOUR_API_KEY` or provide it when
    constructing `Analyzer(api_key)` in your code.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import re
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import requests
from youtube_transcript_api import YouTubeTranscriptApi

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


NumberExtract = Dict[str, object]


def _fetch_transcript(video_id: str, lang: str):
    """Robustly fetch transcript using the instance-based API pattern.

    Attempts to use the `list_transcripts` (or `list`) method on an instance of
    `YouTubeTranscriptApi` and then `fetch()` the specific language transcript.
    """
    from youtube_transcript_api import YouTubeTranscriptApi

    try:
        # Following the pattern suggested by the user/docs for newer/different versions
        api = YouTubeTranscriptApi()

        # Try 'list_transcripts' (standard) or 'list' (alternative)
        if hasattr(api, "list_transcripts"):
            transcript_list = api.list_transcripts(video_id)
        elif hasattr(api, "list"):
            # Some versions or user examples use .list()
            transcript_list = api.list(video_id)
        else:
            # Last resort: try the static method get_transcript if it exists
            # (though the user reported it missing)
            if hasattr(YouTubeTranscriptApi, "get_transcript"):
                return YouTubeTranscriptApi.get_transcript(video_id, languages=[lang])
            raise AttributeError("YouTubeTranscriptApi instance has no 'list_transcripts' or 'list' method")

        # Find the transcript for the requested language and fetch its data
        transcript = transcript_list.find_transcript([lang])
        return transcript.fetch()
    except Exception:
        # Allow the caller to handle failures (e.g. no transcript available)
        raise



class Analyzer:
    def __init__(self, api_key: str, session: Optional[requests.Session] = None):
        self.api_key = api_key
        self.session = session or requests.Session()
        # number pattern: integers, grouped thousands (spaces/commas/dots), decimals
        self._num_re = re.compile(r"\d{1,3}(?:[ \\.,]\d{3})*(?:[\\.,]\d+)?")
        self._playlist_cache: Dict[str, str] = {}

    def get_videos_from_channels(self, channel_ids: Iterable[str], lang: str) -> List[NumberExtract]:
        """Return list of number extracts for the given channels and language.

        Args:
            channel_ids: iterable of YouTube channel IDs.
            lang: transcript language code (e.g., 'en', 'fr').
        """
        results: List[NumberExtract] = []
        for channel_id in channel_ids:
            logger.info("Scanning channel %s", channel_id)
            try:
                video_ids = self._list_channel_uploads(channel_id)
                print(f"Found {len(video_ids)} videos in channel {channel_id}")
            except Exception as e:
                logger.info("Failed to list uploads for channel %s: %s", channel_id, str(e))
                continue

            for vid in video_ids:
                print(f"Processing video {vid}")
                try:
                    extracts = self._scan_video_for_numbers(vid, lang)
                except Exception as e:
                    logger.info("Failed to scan video %s: %s", vid, str(e))
                    extracts = []
                results.extend(extracts)

        logger.info("Found %d extracts", len(results))
        return results

    def _list_channel_uploads(self, channel_id: str, max_results: int = 25) -> List[str]:
        """Return list of video IDs from the channel's uploads playlist (first page).

        This keeps behavior similar to the original script (first 25 videos).
        """
        uploads_pl = self._playlist_cache.get(channel_id)
        if not uploads_pl:
            url = (
                "https://www.googleapis.com/youtube/v3/channels"
                "?part=contentDetails&id={channel}&key={key}"
            ).format(channel=channel_id, key=self.api_key)

            time.sleep(5)
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 403:
                print(f"Access forbidden for channel {channel_id}: {resp.text}")
            resp.raise_for_status()
            data = resp.json()
            items = data.get("items") or []
            if not items:
                raise ValueError("no channel items for %s" % channel_id)

            uploads_pl = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
            self._playlist_cache[channel_id] = uploads_pl

        pl_url = (
            "https://www.googleapis.com/youtube/v3/playlistItems"
            "?part=contentDetails&maxResults={max}&playlistId={pl}&key={key}"
        ).format(max=max_results, pl=uploads_pl, key=self.api_key)

        time.sleep(5)
        resp = self.session.get(pl_url, timeout=10)
        resp.raise_for_status()
        pl_data = resp.json()
        video_ids = [it["contentDetails"]["videoId"] for it in pl_data.get("items", [])]
        return video_ids

    def _scan_video_for_numbers(self, video_id: str, lang: str) -> List[NumberExtract]:
        """Fetch transcript and return extracts containing numbers.

        Each extract is a dict with keys: lang, video_id, timecode, numbers, phrase
        """
        try:
            time.sleep(5)
            transcript = _fetch_transcript(video_id, lang)
            print(f"Scanning video {video_id} for numbers in {lang} transcript")
        except Exception as e:
            logger.info("No transcript for %s in %s", video_id, lang)
            logger.info("Error: %s", str(e))
            return []

        def get_field(item, field, default=""):
            if hasattr(item, "get"):
                return item.get(field, default)
            return getattr(item, field, default)

        extracts: List[NumberExtract] = []
        # iterate with index to grab previous/next snippets for context
        for idx, entry in enumerate(transcript):
            text = (get_field(entry, "text") or "").strip()
            if not text:
                continue
            nums = self._num_re.findall(text)
            if not nums:
                #print(f"No numbers found in snippet: {text}")
                continue

            # build context phrase from previous/current/next lines if available
            parts = []
            if idx - 1 >= 0:
                parts.append(get_field(transcript[idx - 1], "text", ""))
            parts.append(text)
            if idx + 1 < len(transcript):
                parts.append(get_field(transcript[idx + 1], "text", ""))
            phrase = " ".join(p.strip() for p in parts if p).replace(",", "")

            # normalize spaces inside grouped numbers like '1 234' -> '1234'
            normalized_nums = [n.replace(" ", "") for n in nums]

            timecode = max(0, int(get_field(entry, "start", 0)) - 2)

            extracts.append(
                {
                    "lang": lang,
                    "video_id": video_id,
                    "timecode": timecode,
                    "numbers": normalized_nums,
                    "phrase": phrase,
                }
            )
            print(f"Found numbers {normalized_nums} in video {video_id} at {timecode}s: {phrase}")

        return extracts


def read_channels_csv(path: str) -> List[Dict[str, str]]:
    """Read a CSV with header name,id,lang and return rows as dicts."""
    rows: List[Dict[str, str]] = []
    p = Path(path)
    with p.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for r in reader:
            rows.append(r)
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract numeric mentions from YouTube channels")
    parser.add_argument("--key", required=True, help="YouTube Data API key")
    parser.add_argument("--channels-csv", default="channels.csv", help="CSV file with columns name,id,lang")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of channels processed (0=all)")
    parser.add_argument("--out-dir", default="output", help="Output directory for per-language JSON files")
    parser.add_argument(
        "--lang",
        default="all",
        choices=["all", "en", "fr", "ru", "es", "de", "it"],
        help="Filter by language code (default: all). Options: en, fr, ru, es, de, it",
    )
    args = parser.parse_args()

    channels = read_channels_csv(args.channels_csv)
    if args.limit:
        channels = channels[: args.limit]

    # apply CLI language filter if requested
    if args.lang and args.lang.lower() != "all":
        want = args.lang.lower()
        channels = [ch for ch in channels if (ch.get("lang", "").lower() == want)]

    analyzer = Analyzer(args.key)
    # group channels by language to avoid repeated lang calls per channel if desired
    results = []
    for ch in channels:
        ch_id = ch.get("id")
        ch_lang = ch.get("lang", "en")
        if not ch_id:
            continue
        results.extend(analyzer.get_videos_from_channels([ch_id], ch_lang))
    # group results by language and write JSON files per language
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    by_lang = {}
    for entry in results:
        lang = entry.get("lang", "und")
        by_lang.setdefault(lang, []).append(entry)

    for lang, items in by_lang.items():
        out_list = []
        for idx, it in enumerate(items, start=1):
            out_list.append({
                "url": it.get("video_id"),
                "time": int(it.get("timecode", 0)),
                "subs": it.get("phrase", ""),
                "id": idx,
            })

        out_path = out_dir / f"{lang}.json"
        with out_path.open("w", encoding="utf-8") as fh:
            json.dump(out_list, fh, ensure_ascii=False, indent=2)

    # Print brief summary
    for lang, items in by_lang.items():
        logger.info("Wrote %d extracts to %s", len(items), out_dir / f"{lang}.json")