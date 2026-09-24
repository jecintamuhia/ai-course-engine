# local_ai_course_engine

Moodle local plugin that exposes two web service functions Moodle core
does not provide. Core web services cannot set a course section's name
or summary (`core_course_edit_section` only changes visibility, the
marker, or deletes sections), and no core web service can create an
activity module instance. The AI Course Engine backend therefore calls
these functions when publishing an approved curriculum.

## Provided web service functions

| Function | Parameters | Behaviour |
|---|---|---|
| `local_ai_course_engine_update_section` | `courseid`, `section` (number, 0-based), `name`, `summary`, `summaryformat` | Sets the section name/summary; creates the section if it does not exist (extending `numsections` on topics/weeks formats). Requires `moodle/course:update`. |
| `local_ai_course_engine_add_page` | `courseid`, `section` (number, 0-based), `name`, `content`, `contentformat` | Adds a Page activity to the section; creates the section if it does not exist. Requires `mod/page:addinstance`. Returns the new `cmid`. |

## Installation

1. Copy this directory to `moodle/local/ai_course_engine` on the server.
2. Visit the site as an administrator and run the upgrade (the plugin
   registers itself during the normal upgrade step).
3. In Site administration → Plugins → Web services → External services,
   open the external service used by the token and add both
   `local_ai_course_engine_*` functions.
4. Grant the token's service user the capabilities
   `moodle/course:update` and `mod/page:addinstance` (or enable the
   preset capabilities for the service's role).

## Notes

- No database tables, capabilities, settings, or scheduled tasks are
  defined by this plugin; the files `db/access.php`, `db/tasks.php`, and
  `settings.php` declare empty structures by design.
- Test on a staging Moodle instance before enabling on production.