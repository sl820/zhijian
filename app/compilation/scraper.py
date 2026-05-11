"""
Multi-source data scraper for ancient Chinese texts.

This module provides functionality to fetch and process ancient Chinese texts
from various sources including ctext.org, library catalogs, local scans, and custom URLs.
"""

import logging
import re
import os
import pathlib
import urllib.request
import urllib.error
import urllib.parse
import html
import datetime
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Callable, Optional, Dict, Any

logger = logging.getLogger(__name__)


class SourceType(Enum):
    """Enumeration of supported data source types for ancient Chinese texts."""
    LIBRARY_CATALOG = "图书馆目录"
    CTEXT_ORG = "Chinese Text Project - ctext.org"
    DATABASE_API = "数据库API"
    LOCAL_SCAN = "本地扫描件"
    CUSTOM_URL = "自定义URL"


@dataclass
class TextSource:
    """
    Represents a source of ancient Chinese text with metadata.

    Attributes:
        source_type: The type of source (enum value from SourceType)
        source_name: Human-readable name for the source
        url: URL or path to the source
        text_content: The actual text content (may be empty if not yet fetched)
        metadata: Dictionary containing additional metadata (author, title, date, etc.)
        quality_score: Quality assessment score (0.0 to 1.0)
        access_date: Timestamp when the source was accessed
    """
    source_type: SourceType
    source_name: str
    url: str
    text_content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    quality_score: float = 0.0
    access_date: datetime.datetime = field(default_factory=datetime.datetime.now)


class SourceScraper:
    """
    Scraper for fetching ancient Chinese texts from multiple source types.

    This class provides methods to fetch texts from:
    - ctext.org (Chinese Text Project)
    - Custom URLs
    - Library OPAC/digital catalog systems
    - Local image scans (with OCR callback)
    """

    # Supported image file extensions for local scans
    IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.tiff', '.tif', '.bmp', '.gif'}

    # Regex pattern to match Chinese text blocks
    CHINESE_TEXT_PATTERN = re.compile(
        r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff\u3000-\u303f\uff00-\uffef'
        r'\u2000-\u206f\u2190-\u21ff\u2600-\u26ff]+',
        re.UNICODE
    )

    # HTML tag stripper
    HTML_TAG_PATTERN = re.compile(r'<[^>]+>')
    HTML_ENTITY_PATTERN = re.compile(r'&[a-zA-Z]+;|&#\d+;')

    # Pre-compiled patterns for HTML content cleaning
    _SCRIPT_PATTERN = re.compile(r'<script[^>]*>.*?</script>', re.DOTALL | re.IGNORECASE)
    _STYLE_PATTERN = re.compile(r'<style[^>]*>.*?</style>', re.DOTALL | re.IGNORECASE)
    _WHITESPACE_PATTERN = re.compile(r'\n{3,}')
    _MULTI_SPACE_PATTERN = re.compile(r' {2,}')

    def __init__(self, timeout: int = 30, user_agent: str = None):
        """
        Initialize the SourceScraper.

        Args:
            timeout: Request timeout in seconds (default: 30)
            user_agent: Custom User-Agent string for HTTP requests
        """
        self.timeout = timeout
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
        logger.info("SourceScraper initialized with timeout=%d", timeout)

    def _make_request(self, url: str) -> Optional[str]:
        """
        Make an HTTP GET request to the specified URL.

        Args:
            url: The URL to fetch

        Returns:
            The response body as string, or None if request failed
        """
        try:
            request = urllib.request.Request(
                url,
                headers={'User-Agent': self.user_agent}
            )
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                charset = self._detect_charset(response)
                content = response.read()
                return content.decode(charset, errors='replace')
        except urllib.error.HTTPError as e:
            logger.error("HTTP error fetching %s: %d %s", url, e.code, e.reason)
        except urllib.error.URLError as e:
            logger.error("URL error fetching %s: %s", url, e.reason)
        except TimeoutError:
            logger.error("Timeout fetching %s", url)
        except Exception as e:
            logger.error("Unexpected error fetching %s: %s", url, str(e))
        return None

    def _detect_charset(self, response) -> str:
        """
        Detect charset from HTTP response headers or content.

        Args:
            response: urllib response object

        Returns:
            Charset string (defaults to 'utf-8')
        """
        content_type = response.headers.get('Content-Type', '')
        if 'charset=' in content_type:
            charset = content_type.split('charset=')[-1].split(';')[0].strip()
            logger.debug("Detected charset from headers: %s", charset)
            return charset

        # Default fallback
        return 'utf-8'

    def _decode_html_entities(self, text: str) -> str:
        """
        Decode HTML entities in text.

        Args:
            text: Text potentially containing HTML entities

        Returns:
            Text with HTML entities decoded
        """
        # Decode named entities
        text = html.unescape(text)
        # Decode numeric entities
        def replace_numeric_entity(match):
            entity = match.group(0)
            if entity.startswith('&#'):
                try:
                    code = int(entity[2:-1])
                    return chr(code)
                except (ValueError, OverflowError):
                    pass
            return entity
        text = self.HTML_ENTITY_PATTERN.sub(replace_numeric_entity, text)
        return text

    def _extract_chinese_text(self, html_content: str) -> str:
        """
        Extract Chinese text blocks from HTML content.

        Args:
            html_content: HTML content as string

        Returns:
            Extracted Chinese text
        """
        # Remove script and style elements
        content = self._SCRIPT_PATTERN.sub('', html_content)
        content = self._STYLE_PATTERN.sub('', content)

        # Remove HTML tags
        content = self.HTML_TAG_PATTERN.sub(' ', content)

        # Decode HTML entities
        content = self._decode_html_entities(content)

        # Extract Chinese text blocks and join with newlines
        chinese_blocks = self.CHINESE_TEXT_PATTERN.findall(content)
        text = '\n'.join(block.strip() for block in chinese_blocks if block.strip())

        # Clean up whitespace
        text = self._WHITESPACE_PATTERN.sub('\n\n', text)
        text = self._MULTI_SPACE_PATTERN.sub(' ', text)

        return text.strip()

    def fetch_ctext(self, chapter_url: str) -> TextSource:
        """
        Fetch text from ctext.org (Chinese Text Project).

        URL pattern: https://ctext.org/{book-name}/{chapter}/zh

        Args:
            chapter_url: Full URL to a ctext.org chapter page

        Returns:
            TextSource object containing the fetched text and metadata

        Example:
            >>> scraper = SourceScraper()
            >>> result = scraper.fetch_ctext("https://ctext.org/analects/8/zh")
        """
        logger.info("Fetching from ctext.org: %s", chapter_url)

        source_name = "ctext.org"
        metadata = {}

        try:
            # Validate URL format
            parsed = urllib.parse.urlparse(chapter_url)
            if 'ctext.org' not in parsed.netloc:
                logger.warning("URL does not appear to be from ctext.org: %s", chapter_url)

            # Fetch the page
            content = self._make_request(chapter_url)
            if content is None:
                logger.error("Failed to fetch content from %s", chapter_url)
                return TextSource(
                    source_type=SourceType.CTEXT_ORG,
                    source_name=source_name,
                    url=chapter_url,
                    quality_score=0.0
                )

            # Extract book and chapter info from URL
            path_parts = [p for p in parsed.path.split('/') if p]
            if len(path_parts) >= 2:
                metadata['book_name'] = path_parts[0]
                metadata['chapter'] = path_parts[1]
            elif len(path_parts) == 1:
                metadata['book_name'] = path_parts[0]

            # Extract Chinese text from HTML
            text_content = self._extract_chinese_text(content)

            # Calculate quality score based on content length
            quality_score = 0.0
            if text_content:
                length = len(text_content)
                if length > 5000:
                    quality_score = 0.9
                elif length > 1000:
                    quality_score = 0.7
                elif length > 100:
                    quality_score = 0.5
                else:
                    quality_score = 0.3

            # Parse additional metadata from content
            metadata.update(self._parse_ctext_metadata(content))

            logger.info("Successfully fetched %d characters from ctext.org", len(text_content))

            return TextSource(
                source_type=SourceType.CTEXT_ORG,
                source_name=source_name,
                url=chapter_url,
                text_content=text_content,
                metadata=metadata,
                quality_score=quality_score
            )

        except Exception as e:
            logger.error("Error fetching ctext.org chapter: %s", str(e))
            return TextSource(
                source_type=SourceType.CTEXT_ORG,
                source_name=source_name,
                url=chapter_url,
                quality_score=0.0
            )

    def _parse_ctext_metadata(self, content: str) -> Dict[str, Any]:
        """
        Parse metadata from ctext.org page content.

        Args:
            content: HTML content from ctext.org

        Returns:
            Dictionary of extracted metadata
        """
        metadata = {}

        # Try to extract title
        title_match = re.search(r'<title>([^<]+)</title>', content, re.IGNORECASE)
        if title_match:
            metadata['page_title'] = self._decode_html_entities(title_match.group(1).strip())

        # Try to extract main content area info
        # ctext.org typically uses class="ctext" for main content
        if 'class="ctext"' in content or 'id="ctext"' in content:
            metadata['source_format'] = 'ctext standard'

        return metadata

    def fetch_custom_url(self, url: str) -> TextSource:
        """
        Fetch and extract Chinese text from a generic URL.

        Args:
            url: URL to fetch content from

        Returns:
            TextSource object containing the fetched text and metadata

        Example:
            >>> scraper = SourceScraper()
            >>> result = scraper.fetch_custom_url("https://example.com/ancient-text")
        """
        logger.info("Fetching from custom URL: %s", url)

        source_name = "custom"
        metadata = {}

        try:
            # Validate URL
            parsed = urllib.parse.urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                logger.error("Invalid URL format: %s", url)
                return TextSource(
                    source_type=SourceType.CUSTOM_URL,
                    source_name=source_name,
                    url=url,
                    quality_score=0.0
                )

            metadata['domain'] = parsed.netloc
            metadata['path'] = parsed.path

            # Fetch the page
            content = self._make_request(url)
            if content is None:
                logger.error("Failed to fetch content from %s", url)
                return TextSource(
                    source_type=SourceType.CUSTOM_URL,
                    source_name=source_name,
                    url=url,
                    quality_score=0.0
                )

            # Extract Chinese text
            text_content = self._extract_chinese_text(content)

            # Calculate quality score
            quality_score = 0.0
            if text_content:
                length = len(text_content)
                if length > 5000:
                    quality_score = 0.8
                elif length > 1000:
                    quality_score = 0.6
                elif length > 100:
                    quality_score = 0.4
                else:
                    quality_score = 0.2

            # Try to extract title
            title_match = re.search(r'<title>([^<]+)</title>', content, re.IGNORECASE)
            if title_match:
                metadata['page_title'] = self._decode_html_entities(title_match.group(1).strip())

            logger.info("Successfully extracted %d characters from custom URL", len(text_content))

            return TextSource(
                source_type=SourceType.CUSTOM_URL,
                source_name=source_name,
                url=url,
                text_content=text_content,
                metadata=metadata,
                quality_score=quality_score
            )

        except Exception as e:
            logger.error("Error fetching custom URL: %s", str(e))
            return TextSource(
                source_type=SourceType.CUSTOM_URL,
                source_name=source_name,
                url=url,
                quality_score=0.0
            )

    def fetch_library_catalog(
        self,
        catalog_url: str,
        filters: Dict[str, Any] = None
    ) -> List[TextSource]:
        """
        Fetch search results from a library OPAC or digital library catalog.

        Args:
            catalog_url: Base URL for the library catalog search
            filters: Dictionary of search filters (e.g., {'title': '论语', 'author': '孔子'})

        Returns:
            List of TextSource objects representing search results

        Example:
            >>> scraper = SourceScraper()
            >>> results = scraper.fetch_library_catalog(
            ...     "https://library.example.edu/catalog/search",
            ...     {'title': '史记', 'year': '100 BCE'}
            ... )
        """
        logger.info("Fetching library catalog: %s with filters: %s", catalog_url, filters)

        results = []
        filters = filters or {}
        metadata = {'filters_applied': filters}

        try:
            # Build URL with query parameters
            parsed = urllib.parse.urlparse(catalog_url)

            if parsed.query:
                # Append to existing query
                query_params = urllib.parse.parse_qsl(parsed.query)
                query_params.extend(filters.items())
                query_string = urllib.parse.urlencode(query_params)
            else:
                query_string = urllib.parse.urlencode(filters)

            full_url = urllib.parse.urlunparse((
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                query_string,
                parsed.fragment
            ))

            metadata['search_url'] = full_url

            # Fetch the catalog search results
            content = self._make_request(full_url)
            if content is None:
                logger.error("Failed to fetch catalog content from %s", full_url)
                return results

            # Extract Chinese text (for display purposes)
            text_content = self._extract_chinese_text(content)

            # Parse result entries from catalog page
            entries = self._parse_catalog_entries(content)

            for entry in entries:
                entry_metadata = {**metadata, **entry.get('metadata', {})}
                results.append(TextSource(
                    source_type=SourceType.LIBRARY_CATALOG,
                    source_name=entry.get('source_name', 'library'),
                    url=entry.get('url', full_url),
                    text_content=entry.get('text_content', ''),
                    metadata=entry_metadata,
                    quality_score=entry.get('quality_score', 0.5)
                ))

            logger.info("Found %d results from library catalog", len(results))
            return results

        except Exception as e:
            logger.error("Error fetching library catalog: %s", str(e))
            return results

    def _parse_catalog_entries(self, content: str) -> List[Dict[str, Any]]:
        """
        Parse library catalog entries from HTML content.

        This is a basic parser that looks for common catalog entry patterns.
        May need adjustment depending on specific library system.

        Args:
            content: HTML content from library catalog

        Returns:
            List of entry dictionaries
        """
        entries = []

        # Look for common patterns in library catalogs
        # Many catalogs use table rows or list items for results

        # Try to find result items (various common patterns)
        item_patterns = [
            (r'<tr[^>]*class="[^"]*(?:result|item|entry)[^"]*"[^>]*>(.*?)</tr>', 'tr'),
            (r'<li[^>]*class="[^"]*(?:result|item|entry)[^"]*"[^>]*>(.*?)</li>', 'li'),
            (r'<div[^>]*class="[^"]*(?:result|item|entry)[^"]*"[^>]*>(.*?)</div>', 'div'),
        ]

        for pattern, tag_type in item_patterns:
            matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
            if matches:
                for match in matches:
                    entry = self._parse_single_catalog_entry(match, tag_type)
                    if entry:
                        entries.append(entry)
                if entries:
                    break

        return entries

    def _parse_single_catalog_entry(self, entry_html: str, tag_type: str) -> Optional[Dict[str, Any]]:
        """
        Parse a single catalog entry from HTML fragment.

        Args:
            entry_html: HTML fragment for single entry
            tag_type: Type of HTML tag ('tr', 'li', 'div')

        Returns:
            Dictionary with entry data or None
        """
        entry = {'metadata': {}}

        # Extract title (common patterns)
        title_patterns = [
            r'<title>([^<]+)</title>',
            r'class="[^"]*title[^"]*"[^>]*>([^<]+)',
            r'<h[1-6][^>]*>([^<]+)</h[1-6]>',
        ]
        for pattern in title_patterns:
            match = re.search(pattern, entry_html, re.IGNORECASE)
            if match:
                entry['source_name'] = self._decode_html_entities(match.group(1).strip())
                break

        # Extract links
        link_match = re.search(r'href="([^"]+)"', entry_html)
        if link_match:
            entry['url'] = link_match.group(1)
            # Make relative URLs absolute
            if not entry['url'].startswith(('http://', 'https://')):
                entry['url'] = 'https://example.edu' + entry['url']

        # Extract Chinese text content
        entry['text_content'] = self._extract_chinese_text(entry_html)

        # Set quality score based on content
        if entry['text_content']:
            entry['quality_score'] = 0.6
        else:
            entry['quality_score'] = 0.3

        return entry

    def fetch_local_scan(
        self,
        scan_dir: str,
        ocr_callback: Callable[[str], str] = None
    ) -> List[TextSource]:
        """
        Scan a directory for image files and apply OCR to extract text.

        Args:
            scan_dir: Directory path containing image files
            ocr_callback: Optional callback function that takes an image path
                          and returns OCR text. If not provided, basic file
                          metadata will be returned instead.

        Returns:
            List of TextSource objects for each scanned image

        Example:
            >>> scraper = SourceScraper()
            >>> def my_ocr(image_path):
            ...     # Use Tesseract or other OCR engine
            ...     return pytesseract.image_to_string(Image.open(image_path), lang='chi_sim')
            >>> results = scraper.fetch_local_scan("/path/to/scans", ocr_callback=my_ocr)
        """
        logger.info("Scanning local directory: %s", scan_dir)

        results = []
        scan_path = pathlib.Path(scan_dir)

        if not scan_path.exists():
            logger.error("Scan directory does not exist: %s", scan_dir)
            return results

        if not scan_path.is_dir():
            logger.error("Path is not a directory: %s", scan_dir)
            return results

        try:
            # Find all image files in directory
            image_files = []
            for ext in self.IMAGE_EXTENSIONS:
                image_files.extend(scan_path.glob(f'**/*{ext}'))
                image_files.extend(scan_path.glob(f'**/*{ext.upper()}'))

            # Sort by filename
            image_files.sort()

            logger.info("Found %d image files in %s", len(image_files), scan_dir)

            for image_file in image_files:
                try:
                    file_metadata = {
                        'filename': image_file.name,
                        'filepath': str(image_file.absolute()),
                        'filesize': image_file.stat().st_size,
                        'extension': image_file.suffix.lower()
                    }

                    if ocr_callback is not None:
                        # Apply OCR callback
                        logger.debug("Applying OCR to: %s", image_file.name)
                        try:
                            text_content = ocr_callback(str(image_file))
                        except Exception as ocr_error:
                            logger.error("OCR failed for %s: %s", image_file.name, str(ocr_error))
                            text_content = ""
                    else:
                        # No OCR callback - use empty content
                        text_content = ""
                        file_metadata['note'] = 'No OCR callback provided'

                    # Calculate quality score
                    quality_score = 0.0
                    if ocr_callback and text_content:
                        chinese_chars = self.CHINESE_TEXT_PATTERN.findall(text_content)
                        if len(chinese_chars) > 100:
                            quality_score = 0.8
                        elif len(chinese_chars) > 10:
                            quality_score = 0.5
                        else:
                            quality_score = 0.3
                    elif text_content:
                        quality_score = 0.4

                    results.append(TextSource(
                        source_type=SourceType.LOCAL_SCAN,
                        source_name=image_file.stem,
                        url=str(image_file.absolute()),
                        text_content=text_content,
                        metadata=file_metadata,
                        quality_score=quality_score
                    ))

                except Exception as e:
                    logger.error("Error processing image %s: %s", image_file.name, str(e))
                    continue

            logger.info("Processed %d images from local scan", len(results))
            return results

        except Exception as e:
            logger.error("Error scanning directory %s: %s", scan_dir, str(e))
            return results


# Convenience functions for quick access

def fetch_ctext_chapter(chapter_url: str) -> TextSource:
    """
    Convenience function to fetch a single ctext.org chapter.

    Args:
        chapter_url: URL to ctext.org chapter

    Returns:
        TextSource with fetched content
    """
    scraper = SourceScraper()
    return scraper.fetch_ctext(chapter_url)


def fetch_url(url: str) -> TextSource:
    """
    Convenience function to fetch and extract Chinese text from any URL.

    Args:
        url: URL to fetch

    Returns:
        TextSource with fetched content
    """
    scraper = SourceScraper()
    return scraper.fetch_custom_url(url)


if __name__ == '__main__':
    # Example usage and basic tests
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("SourceScraper module for ancient Chinese texts")
    print("=" * 50)
    print("Available source types:")
    for st in SourceType:
        print(f"  - {st.name}: {st.value}")
    print()
    print("Usage example:")
    print("  scraper = SourceScraper()")
    print("  result = scraper.fetch_ctext('https://ctext.org/analects/8/zh')")
    print("  print(result.text_content)")
