"""
like.forms
~~~~~~~~~~

Forms used to like/unlike a post. Their only real job is to carry the
CSRF token - which post to (un)like comes from the URL.

:copyright: (c) 2026 by Peter Justin.
:license: BSD License, see LICENSE for more details.
"""

from flask_wtf import FlaskForm


class LikeActionForm(FlaskForm):
    """Used in _like_button.html to like or unlike a post.
    It just contains the hidden CSRF field
    """
