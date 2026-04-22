"""
Migration and export tool: academic_knowledge_graph.json ↔ academic_knowledge_graph.db

Commands:
    python migrate_json_to_sqlite.py migrate              # JSON → SQLite (one-time)
    python migrate_json_to_sqlite.py export-json ...     # SQLite → JSON
    python migrate_json_to_sqlite.py export-csv ...      # SQLite → CSV
    python migrate_json_to_sqlite.py export-txt ...      # SQLite → TXT
"""

import json
import os
import sys
import argparse
import csv
from pathlib import Path
from backend import OUTPUT_PATH, DATA_FILE_PATH
from db_sqlite import upsert_paper, get_paper, DB_PATH

JSON_PATH = DATA_FILE_PATH


# ============================================================================
# Migration: JSON → SQLite
# ============================================================================

def migrate():
    """Migrate academic_knowledge_graph.json to SQLite database."""
    if not os.path.exists(JSON_PATH):
        print(f"JSON file not found: {JSON_PATH}")
        sys.exit(1)

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        db = json.load(f)

    total = len(db)
    print(f"Migrating {total} papers from JSON → SQLite ({DB_PATH}) ...")

    for i, paper_data in enumerate(db.values(), 1):
        upsert_paper(paper_data)
        if i % 50 == 0 or i == total:
            print(f"  {i}/{total}")

    print("Migration complete.")


# ============================================================================
# Helper: Load DOI list
# ============================================================================

def load_doi_list(doi_file: str | None, doi_args: list | None) -> list[str]:
    """Load DOI list from file or command-line arguments."""
    dois = []

    # From --doi arguments
    if doi_args:
        dois.extend(doi_args)

    # From file
    if doi_file:
        if not os.path.exists(doi_file):
            print(f"❌ File not found: {doi_file}")
            sys.exit(1)

        with open(doi_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if line and not line.startswith("#"):
                    dois.append(line)

    # Remove duplicates while preserving order
    seen = set()
    unique_dois = []
    for doi in dois:
        if doi not in seen:
            seen.add(doi)
            unique_dois.append(doi)

    if not unique_dois:
        print("❌ No DOIs provided")
        sys.exit(1)

    return unique_dois


# ============================================================================
# Export functions
# ============================================================================

def export_to_json(dois: list[str], output_file: str):
    """Export specified DOIs from SQLite to JSON format."""
    print(f"📤 Exporting {len(dois)} papers to JSON: {output_file}")

    papers_dict = {}
    found_count = 0

    for doi in dois:
        paper = get_paper(doi)
        if paper:
            papers_dict[doi] = paper
            found_count += 1
        else:
            print(f"  ⚠️  Not found: {doi}")

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(papers_dict, f, ensure_ascii=False, indent=2)

    print(f"✅ Exported {found_count}/{len(dois)} papers to {output_file}")


def export_to_csv(dois: list[str], output_file: str):
    """Export specified DOIs from SQLite to CSV format."""
    print(f"📤 Exporting {len(dois)} papers to CSV: {output_file}")

    found_count = 0

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        # Header
        writer.writerow([
            "DOI",
            "Title",
            "Year",
            "Journal",
            "Authors",
            "Forward Citations",
            "Backward Citations",
            "Last Updated"
        ])

        for doi in dois:
            paper = get_paper(doi)
            if paper:
                meta = paper.get("metadata", {})
                authors_str = "; ".join(meta.get("authors", []))
                forward_str = "; ".join(paper.get("forward", []))
                backward_str = "; ".join(paper.get("backward", []))

                writer.writerow([
                    doi,
                    meta.get("title", ""),
                    meta.get("year", ""),
                    meta.get("journal", ""),
                    authors_str,
                    forward_str,
                    backward_str,
                    paper.get("last_updated", "")
                ])
                found_count += 1
            else:
                print(f"  ⚠️  Not found: {doi}")

    print(f"✅ Exported {found_count}/{len(dois)} papers to {output_file}")


def export_to_txt(dois: list[str], output_file: str, key_list: list[str] | None = None):
    """Export specified DOIs from SQLite to TXT format.

    Args:
        dois: List of DOI strings to export
        output_file: Output file path
        key_list: Which fields to include. Default: ['doi'] for simple DOI list.
                  Options: 'doi', 'title', 'year', 'journal', 'authors', 'forward', 'backward'
                  Example: ['doi', 'title', 'year'] or just ['doi'] for DOI list only
    """
    if key_list is None:
        key_list = ['doi']

    # Normalize key_list
    valid_keys = {'doi', 'title', 'year', 'journal', 'authors', 'forward', 'backward', 'last_updated'}
    key_list = [k for k in key_list if k in valid_keys]
    if not key_list:
        key_list = ['doi']

    is_simple_list = key_list == ['doi']

    print(f"📤 Exporting {len(dois)} papers to TXT: {output_file}")
    print(f"   Fields: {', '.join(key_list)}")

    found_count = 0

    with open(output_file, "w", encoding="utf-8") as f:
        if is_simple_list:
            # Simple DOI list format (like doi_list.txt)
            f.write("# DOI List Export\n")
            f.write(f"# Generated: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# Total DOIs: {len(dois)}\n\n")

            for doi in dois:
                paper = get_paper(doi)
                if paper:
                    f.write(f"{doi}\n")
                    found_count += 1
                else:
                    # Still include in list but with comment
                    f.write(f"# {doi}  (not found)\n")
                    print(f"  ⚠️  Not found: {doi}")
        else:
            # Detailed format with selected fields
            f.write("=" * 80 + "\n")
            f.write("Academic Knowledge Graph Export\n")
            f.write("=" * 80 + "\n\n")

            for i, doi in enumerate(dois, 1):
                paper = get_paper(doi)
                if paper:
                    meta = paper.get("metadata", {})

                    f.write(f"\n[{i}] ")

                    # Always include DOI as header
                    f.write(f"DOI: {doi}\n")
                    f.write("-" * 80 + "\n")

                    # Output requested fields
                    if 'title' in key_list and meta.get("title"):
                        f.write(f"Title:   {meta['title']}\n")

                    if 'year' in key_list and meta.get("year"):
                        f.write(f"Year:    {meta['year']}\n")

                    if 'journal' in key_list and meta.get("journal"):
                        f.write(f"Journal: {meta['journal']}\n")

                    if 'authors' in key_list and meta.get("authors"):
                        authors = ", ".join(meta["authors"])
                        f.write(f"Authors: {authors}\n")

                    if 'forward' in key_list:
                        forward = paper.get("forward", [])
                        if forward:
                            f.write(f"\nForward Citations ({len(forward)}):\n")
                            for cite in forward:
                                f.write(f"  - {cite}\n")

                    if 'backward' in key_list:
                        backward = paper.get("backward", [])
                        if backward:
                            f.write(f"\nBackward Citations ({len(backward)}):\n")
                            for cite in backward:
                                f.write(f"  - {cite}\n")

                    if 'last_updated' in key_list and paper.get("last_updated"):
                        f.write(f"\nLast Updated: {paper['last_updated']}\n")

                    found_count += 1
                else:
                    f.write(f"\n[{i}] DOI: {doi}\n")
                    f.write("-" * 80 + "\n")
                    f.write("⚠️  Not found in database\n")
                    print(f"  ⚠️  Not found: {doi}")

            f.write("\n" + "=" * 80 + "\n")
            f.write(f"Total: {found_count}/{len(dois)} papers found\n")
            f.write("=" * 80 + "\n")

    print(f"✅ Exported {found_count}/{len(dois)} papers to {output_file}")


# ============================================================================
# Main CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Migration and export tool for academic knowledge graph",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # One-time migration from JSON to SQLite
  python migrate_json_to_sqlite.py migrate

  # Export to JSON using DOI file
  python migrate_json_to_sqlite.py export-json --file dois.txt --output export.json

  # Export to CSV with specific DOIs
  python migrate_json_to_sqlite.py export-csv --doi 10.1038/nphys2439 10.1103/PhysRevLett.92.185001 --output papers.csv

  # Export to TXT combining file and command-line DOIs
  python migrate_json_to_sqlite.py export-txt --file seeds.txt --doi 10.1234/example --output papers.txt
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Sub-command")

    # migrate command
    migrate_parser = subparsers.add_parser("migrate", help="Migrate JSON to SQLite (one-time)")

    # export-json command
    json_parser = subparsers.add_parser("export-json", help="Export SQLite to JSON")
    json_parser.add_argument("--file", type=str, help="DOI list file")
    json_parser.add_argument("--doi", nargs="+", help="DOI(s) to export")
    json_parser.add_argument("--output", type=str, default="export.json", help="Output file (default: export.json)")

    # export-csv command
    csv_parser = subparsers.add_parser("export-csv", help="Export SQLite to CSV")
    csv_parser.add_argument("--file", type=str, help="DOI list file")
    csv_parser.add_argument("--doi", nargs="+", help="DOI(s) to export")
    csv_parser.add_argument("--output", type=str, default="export.csv", help="Output file (default: export.csv)")

    # export-txt command
    txt_parser = subparsers.add_parser("export-txt", help="Export SQLite to TXT")
    txt_parser.add_argument("--file", type=str, help="DOI list file")
    txt_parser.add_argument("--doi", nargs="+", help="DOI(s) to export")
    txt_parser.add_argument("--output", type=str, default="export.txt", help="Output file (default: export.txt)")
    txt_parser.add_argument(
        "--keys",
        nargs="+",
        default=["doi"],
        help="Fields to include: doi, title, year, journal, authors, forward, backward, last_updated (default: ['doi'] for simple DOI list)"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "migrate":
        migrate()

    elif args.command == "export-json":
        dois = load_doi_list(args.file, args.doi)
        export_to_json(dois, args.output)

    elif args.command == "export-csv":
        dois = load_doi_list(args.file, args.doi)
        export_to_csv(dois, args.output)

    elif args.command == "export-txt":
        dois = load_doi_list(args.file, args.doi)
        export_to_txt(dois, args.output, key_list=args.keys)


if __name__ == "__main__":
    main()
