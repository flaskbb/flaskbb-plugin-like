Changelog
=========

Here you can see the full list of changes between each release.

Version 1.0.0
-------------

Unreleased

* Forked from flaskbb-plugin-vanity and renamed to flaskbb-plugin-like.
* Fix authors' primary groups being mismatched in topic views by switching
  the post/user eager loading from `lazy='joined'` to `lazy='selectin'`
  (flaskbb/flaskbb#503). `selectin` batches the extra load into its own
  query instead of folding into flaskbb's own outerjoin, so it can't shift
  columns in a query it doesn't own.
* Keep the stored `likes_given`/`likes_received` counters on `User` for
  read performance, but maintain them from `after_insert`/`after_delete`
  events on `PostLike` with SQL-expression increments instead of the old
  read-modify-write in the view, so cascading post/user deletes stay
  accounted for and concurrent likes can't lose a count. Adds
  `recalculate_like_counts()` to resync a user whose counters drifted.
* Like and unlike without reloading the topic page
* Modernize the plugin for the current pluggy hook / settings registry
  API: explicit `hookimpl` markers, a `SettingGroup` (adds an
  `ALLOW_SELF_LIKE` setting), and a squashed migration with
  `ondelete=CASCADE` foreign keys.

Version 0.0.1
-------------

Released August 24, 2018

* Add 'Liked posts' section to user pages.

Released August 21, 2018

* Fix bug where users' primary groups would be mismatched in topics (see
  https://github.com/flaskbb/flaskbb/issues/503)

Released July 30, 2018

* Initial release, as flaskbb-plugin-vanity.
