#!/usr/bin/env python3
from dataclasses import dataclass

import argparse
import json
import os
import sys

from diskcache import Cache
from github import Github
from thefuzz import fuzz

SEARCH_CONFIDENCE_MIN = 60
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
CACHE_EXPIRATION = (24*60*60)  # Expire after 24 hours
CACHE = Cache("cache")

TYPE_ICONS = {
    'maintained': '🔧',
    'starred': '⭐',
    'watched': '👀'
}


@dataclass
class AlfredSuggestion:
    """Class for keeping track of an Alfred suggestion item."""
    # pylint: disable=too-many-arguments
    title: str
    arg: str
    subtitle: str = ""
    valid: bool = True
    variables: dict = None


class GenericSerializer(json.JSONEncoder):
    def default(self, o):
        return o.__dict__


@CACHE.memoize(expire=CACHE_EXPIRATION)
def get_github_repositories():
    repositories = {
        'maintained': [],
        'starred': [],
        'watched': []
    }
    github = Github(GITHUB_TOKEN)
    user = github.get_user()
    for repo in user.get_repos():
        repositories['maintained'].append(repo)

    for repo in user.get_watched():
        repositories['watched'].append(repo)

    for repo in user.get_starred():
        repositories['starred'].append(repo)

    return repositories


def get_alfred_suggestions(search_term):
    suggestions = []

    github_repositories = get_github_repositories()

    for repo_type, repos in github_repositories.items():
        for repo in repos:
            if repo.full_name in [suggestion.variables['full_name'] for suggestion in suggestions]:
                continue

            search_confidence = fuzz.partial_ratio(
                repo.full_name, search_term)

            if search_confidence >= SEARCH_CONFIDENCE_MIN:
                suggestions.append(
                    AlfredSuggestion(
                        title=f'{TYPE_ICONS[repo_type]} {repo.full_name}',
                        subtitle=repo.description if repo.description else "No description available.",
                        arg=repo.html_url,
                        variables={
                            'confidence': search_confidence,
                            'full_name': repo.full_name,
                            'issues_url': f'{repo.html_url}/issues',
                            'pr_url': f'{repo.html_url}/pulls'
                        }
                    )
                )

    suggestions.sort(key=lambda x: x.variables['confidence'], reverse=True)

    if len(suggestions) == 0:
        suggestions = [
            AlfredSuggestion(
                title=f'No results found for "{search_term}"',
                arg=None
            )
        ]

    response = json.dumps(
        {
            "items": suggestions
        },
        cls=GenericSerializer
    )

    return response


def validate_preconditions():
    if not GITHUB_TOKEN:
        sys.exit('No GitHub token set.')


def main():
    validate_preconditions()

    parser = argparse.ArgumentParser(
        description="Find your starred/watched/maintained GitHub repositories.")

    subparsers = parser.add_subparsers(dest="command")

    parser_search = subparsers.add_parser(
        "search",
        help="Search repositories",
    )

    parser_search.add_argument(
        "query",
        help="The needle to search for.",
        type=str
    )

    parser_search.add_argument(
        "--recreate_cache",

        help="Recreate any existing cached records.",
        action="store_true"
    )

    # pylint: disable=unused-variable
    update_cache_parser = subparsers.add_parser(
        "update-cache",
        help="Force the local cache to be updated."
    )

    args = parser.parse_args()

    if args.command == "search":
        search_term = args.query
        if args.recreate_cache:
            CACHE.clear()
        print(get_alfred_suggestions(search_term))
    elif args.command == "update-cache":
        CACHE.clear()
        get_github_repositories()


if __name__ == '__main__':
    main()
