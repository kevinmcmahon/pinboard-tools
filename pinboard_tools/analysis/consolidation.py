# ABOUTME: Tag consolidation and merging functionality
# ABOUTME: Handles merging similar tags and updating bookmarks

from typing import Any

from ..database.models import Database
from ..utils.display import print_info, print_success, print_warning
from .similarity import TagSimilarityDetector


class TagConsolidator:
    """Consolidate and merge similar tags"""

    def __init__(self, db: Database):
        self.db = db
        self.merge_history: list[dict[str, Any]] = []

    def analyze_tags(self) -> dict[str, Any]:
        """Analyze all tags and find consolidation opportunities"""
        # Get all tags with counts
        cursor = self.db.execute("""
            SELECT t.name, COUNT(bt.bookmark_id) as count
            FROM tags t
            LEFT JOIN bookmark_tags bt ON t.id = bt.tag_id
            GROUP BY t.id
            ORDER BY count DESC
        """)

        tags_with_counts = {row["name"]: row["count"] for row in cursor}
        tags = list(tags_with_counts.keys())

        # Find similarities
        detector = TagSimilarityDetector(tags)
        similarities = detector.find_all_similarities()
        groups = detector.find_tag_groups()

        # Analyze co-occurrence
        co_occurrence = self._analyze_co_occurrence(limit=50)

        return {
            "total_tags": len(tags),
            "tags_with_counts": tags_with_counts,
            "similarities": similarities,
            "groups": groups,
            "co_occurrence": co_occurrence,
            "consolidation_suggestions": self._generate_suggestions(
                tags_with_counts, similarities, co_occurrence
            ),
        }

    def merge_tags(
        self, old_tag: str, new_tag: str, dry_run: bool = False
    ) -> dict[str, Any]:
        """Merge old_tag into new_tag"""
        print_info(f"Merging '{old_tag}' -> '{new_tag}'")

        # Get tag IDs
        cursor = self.db.execute("SELECT id FROM tags WHERE name = ?", (old_tag,))
        old_tag_row = cursor.fetchone()
        if not old_tag_row:
            print_warning(f"Tag '{old_tag}' not found")
            return {"success": False, "error": "Old tag not found"}

        old_tag_id = old_tag_row["id"]

        # Ensure new tag exists
        if not dry_run:
            self.db.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (new_tag,))

        cursor = self.db.execute("SELECT id FROM tags WHERE name = ?", (new_tag,))
        new_tag_row = cursor.fetchone()
        new_tag_id = new_tag_row["id"] if new_tag_row else None

        # Find bookmarks to update
        cursor = self.db.execute(
            """
            SELECT DISTINCT bookmark_id
            FROM bookmark_tags
            WHERE tag_id = ?
        """,
            (old_tag_id,),
        )

        bookmark_ids = [row["bookmark_id"] for row in cursor.fetchall()]
        update_count = len(bookmark_ids)

        if not dry_run and new_tag_id:
            # Update bookmark_tags table for each bookmark
            for bookmark_id in bookmark_ids:
                # Remove old tag association
                self.db.execute(
                    "DELETE FROM bookmark_tags WHERE bookmark_id = ? AND tag_id = ?",
                    (bookmark_id, old_tag_id),
                )

                # Add new tag association (if not already exists)
                self.db.execute(
                    "INSERT OR IGNORE INTO bookmark_tags (bookmark_id, tag_id) VALUES (?, ?)",
                    (bookmark_id, new_tag_id),
                )

                # Mark bookmark for sync (triggers will handle this automatically, but let's be explicit)
                self.db.execute(
                    "UPDATE bookmarks SET sync_status = 'pending_local' WHERE id = ? AND sync_status = 'synced'",
                    (bookmark_id,),
                )

            # Delete old tag if no longer used
            cursor = self.db.execute(
                "SELECT COUNT(*) as count FROM bookmark_tags WHERE tag_id = ?",
                (old_tag_id,),
            )
            if cursor.fetchone()["count"] == 0:
                self.db.execute("DELETE FROM tags WHERE id = ?", (old_tag_id,))

            # Record merge in history
            self.db.execute(
                """
                INSERT INTO tag_merges (old_tag, new_tag, bookmarks_updated)
                VALUES (?, ?, ?)
            """,
                (old_tag, new_tag, update_count),
            )

            self.db.commit()
            print_success(f"Merged {update_count} bookmarks")
        else:
            print_info(f"Would merge {update_count} bookmarks (dry run)")

        return {"success": True, "bookmarks_updated": update_count, "dry_run": dry_run}

    def _analyze_co_occurrence(self, limit: int = 20) -> list[dict[str, Any]]:
        """Find tags that frequently appear together"""
        cursor = self.db.execute(
            """
            SELECT
                t1.name as tag1,
                t2.name as tag2,
                COUNT(*) as count
            FROM bookmark_tags bt1
            JOIN bookmark_tags bt2 ON bt1.bookmark_id = bt2.bookmark_id
            JOIN tags t1 ON bt1.tag_id = t1.id
            JOIN tags t2 ON bt2.tag_id = t2.id
            WHERE bt1.tag_id < bt2.tag_id
            GROUP BY bt1.tag_id, bt2.tag_id
            ORDER BY count DESC
            LIMIT ?
        """,
            (limit,),
        )

        return [dict(row) for row in cursor]

    def _generate_suggestions(
        self,
        tags_with_counts: dict[str, int],
        similarities: dict[str, list[tuple[str, float, str]]],
        co_occurrence: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Generate consolidation suggestions based on analysis"""
        suggestions: list[dict[str, Any]] = []

        self._add_merge_suggestions(suggestions, tags_with_counts, similarities)
        self._add_rare_tag_suggestions(suggestions, tags_with_counts, similarities)

        return self._remove_duplicate_suggestions(suggestions)

    def _add_merge_suggestions(
        self,
        suggestions: list[dict[str, Any]],
        tags_with_counts: dict[str, int],
        similarities: dict[str, list[tuple[str, float, str]]],
    ) -> None:
        """Add merge suggestions for similar tags where one is significantly more popular"""
        for tag1, similar_tags in similarities.items():
            count1 = tags_with_counts.get(tag1, 0)

            for tag2, similarity, similarity_type in similar_tags:
                count2 = tags_with_counts.get(tag2, 0)

                # Suggest merging if one tag is used much more
                if count1 > count2 * 3 and count2 > 0:
                    suggestions.append(
                        {
                            "type": "merge_to_popular",
                            "from": tag2,
                            "to": tag1,
                            "reason": f"{similarity_type} (similarity: {similarity:.2f})",
                            "from_count": count2,
                            "to_count": count1,
                        }
                    )
                elif count2 > count1 * 3 and count1 > 0:
                    suggestions.append(
                        {
                            "type": "merge_to_popular",
                            "from": tag1,
                            "to": tag2,
                            "reason": f"{similarity_type} (similarity: {similarity:.2f})",
                            "from_count": count1,
                            "to_count": count2,
                        }
                    )

    def _add_rare_tag_suggestions(
        self,
        suggestions: list[dict[str, Any]],
        tags_with_counts: dict[str, int],
        similarities: dict[str, list[tuple[str, float, str]]],
    ) -> None:
        """Add suggestions for consolidating rarely used tags"""
        rare_threshold = 3
        for tag, count in tags_with_counts.items():
            if count <= rare_threshold and count > 0:
                # Find if there's a similar popular tag
                if tag in similarities:
                    for similar_tag, _, _ in similarities[tag]:
                        if tags_with_counts.get(similar_tag, 0) > 10:
                            suggestions.append(
                                {
                                    "type": "consolidate_rare",
                                    "from": tag,
                                    "to": similar_tag,
                                    "reason": "Rarely used similar tag",
                                    "from_count": count,
                                    "to_count": tags_with_counts[similar_tag],
                                }
                            )
                            break

    def _remove_duplicate_suggestions(
        self, suggestions: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Remove duplicate suggestions"""
        seen = set()
        unique_suggestions = []
        for s in suggestions:
            key = (s["from"], s["to"])
            if key not in seen:
                seen.add(key)
                unique_suggestions.append(s)

        return unique_suggestions
