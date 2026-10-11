import pytest
from flaskbb.forum.models import Post
from tests.fixtures.app import *
from tests.fixtures.forum import *
from tests.fixtures.user import *

from like.models import PostLike


@pytest.fixture(scope="package")
def tested_plugins():
    return ["like"]


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
