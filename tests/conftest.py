import pytest
from flaskbb.core.settings import setting_registry
from flaskbb.forum.models import Post
from tests.fixtures.app import *
from tests.fixtures.forum import *
from tests.fixtures.user import *

from like import SETTINGS
from like.models import PostLike
from like.views import like_bp

# Normally flaskbb_load_setting_groups is called by pluggy during
# create_app(), which only happens if `like` is entry-point installed (see
# README.md). Registering it here directly, once per test session, gets
# LIKE_ALLOW_SELF_LIKE into the registry for default_settings/flaskbb_config
# without requiring that install.
try:
    setting_registry.register_group(SETTINGS, is_plugin=True)
except ValueError:
    pass


@pytest.fixture(scope="package", autouse=True)
def _register_like_blueprint(application):
    """Normally flaskbb_load_blueprints registers this for us. Doing it
    here directly makes like's own templates resolvable (post.url and
    friends need like.like_post/like.unlike_post/like.liked_posts to
    exist) without requiring an entry-point install."""
    if "like" not in application.blueprints:
        application.register_blueprint(like_bp, url_prefix="/like")


def _reply(topic, user):
    """A reply post in ``topic`` - liked_post attaches to this, not the
    first post, so cascade-delete tests don't get entangled with
    Post.delete() redirecting to Topic.delete() for a topic's first
    post."""
    return Post(content="Test reply").save(user=user, topic=topic)


@pytest.fixture
def liked_post(topic, user, moderator_user):
    """A reply post in ``topic``, liked once by ``moderator_user``."""
    post = _reply(topic, user)
    PostLike(post_id=post.id, user_id=moderator_user.id).save()
    return post
