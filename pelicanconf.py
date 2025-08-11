import json
import pathlib

package_json = json.loads(pathlib.Path("package.json").read_text())
BOOTSTRAP_VERSION = package_json.get("dependencies").get("bootstrap")

SITENAME = "Accio Jacksons!"
SITESUBTITLE = "An 11-inch holly blog with a phoenix feather core"
AUTHOR = "Rebecca and William Jackson"

# WARNING Feeds generated without SITEURL set properly may not be valid
FEED_DOMAIN = "https://accio.subtlecoolness.com"
SITEURL = FEED_DOMAIN

# WARNING No timezone information specified in the settings. Assuming your timezone is UTC for feed generation.
TIMEZONE = "America/Chicago"

# Default path is working directory, so change to "content" directory
PATH = "content"

# Article urls
ARTICLE_SAVE_AS = "{date:%Y/%m/%d}/{urlname}.html"
ARTICLE_URL = "{date:%Y/%m/%d}/{urlname}"

# Set the theme and some customer variables used in the theme
THEME = "themes/accio"
DEBUG_LAYOUT = False

# I don't want to remember to delete the output directory before every build
DELETE_OUTPUT_DIRECTORY = True

# Some files need to land in special locations
EXTRA_PATH_METADATA = {"images/gitignore.txt": {"path": ".gitignore"}}

# I don't want the default archive, author, category, and tag pages
ARCHIVES_SAVE_AS = ""
AUTHOR_SAVE_AS = ""
AUTHORS_SAVE_AS = ""
CATEGORIES_SAVE_AS = ""
CATEGORY_SAVE_AS = ""
TAG_SAVE_AS = ""
TAGS_SAVE_AS = ""

# Disable some Atom and RSS feeds
AUTHOR_FEED_ATOM = None
AUTHOR_FEED_RSS = None
CATEGORY_FEED_ATOM = None
TRANSLATION_FEED_ATOM = None

DEFAULT_DATE_FORMAT = "%Y-%m-%d"
FEED_ALL_ATOM = "feeds/all.atom.xml"
SLUGIFY_SOURCE = "basename"
