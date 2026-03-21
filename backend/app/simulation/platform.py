from __future__ import annotations

from oasis.social_platform.platform import Platform


class DeliberationPlatform(Platform):
    def __init__(self, *, db_path: str, channel):
        super().__init__(
            db_path=db_path,
            channel=channel,
            recsys_type="random",
            refresh_rec_post_count=0,
            max_rec_post_len=0,
            following_post_count=0,
            allow_self_rating=True,
            show_score=False,
        )

    async def update_rec_table(self):
        # The deliberation room is group-first, so recommendation-system
        # refreshes are intentionally disabled.
        return None
