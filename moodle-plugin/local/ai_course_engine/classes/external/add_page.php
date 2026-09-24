<?php
namespace local_ai_course_engine\external;

defined('MOODLE_INTERNAL') || die();

use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_single_structure;
use core_external\external_value;

class add_page extends external_api {
    public static function add_page_parameters(): external_function_parameters {
        return new external_function_parameters([
            'courseid' => new external_value(PARAM_INT, 'The course id'),
            'section' => new external_value(PARAM_INT, 'The zero-based section number'),
            'name' => new external_value(PARAM_TEXT, 'The page activity name'),
            'content' => new external_value(PARAM_RAW, 'The page content'),
            'contentformat' => new external_value(
                PARAM_INT,
                'The content text format',
                VALUE_DEFAULT,
                FORMAT_HTML
            ),
        ]);
    }

    public static function add_page(
        int $courseid,
        int $section,
        string $name,
        string $content,
        int $contentformat = FORMAT_HTML
    ): array {
        global $CFG, $DB;

        $params = self::validate_parameters(
            self::add_page_parameters(),
            [
                'courseid' => $courseid,
                'section' => $section,
                'name' => $name,
                'content' => $content,
                'contentformat' => $contentformat,
            ]
        );

        require_once($CFG->dirroot . '/course/lib.php');
        require_once($CFG->dirroot . '/course/modlib.php');

        $course = get_course($params['courseid']);
        if (!$course) {
            throw new \moodle_exception(
                'course_not_found',
                'local_ai_course_engine',
                '',
                $params['courseid']
            );
        }

        require_login($course);
        require_capability('mod/page:addinstance', \context_course::instance($course->id));

        if (!$DB->get_record('modules', ['name' => 'page', 'visible' => 1])) {
            throw new \moodle_exception('page_module_disabled', 'local_ai_course_engine');
        }

        $sectionrecord = $DB->get_record('course_sections', [
            'course' => $course->id,
            'section' => $params['section'],
        ]);

        if (!$sectionrecord) {
            course_create_sections_if_missing($course->id, $params['section']);
            $sectionrecord = $DB->get_record('course_sections', [
                'course' => $course->id,
                'section' => $params['section'],
            ]);
        }

        if (!$sectionrecord) {
            throw new \moodle_exception(
                'section_not_found',
                'local_ai_course_engine',
                '',
                $params['section']
            );
        }

        require_once($CFG->libdir . '/resourcelib.php');

        $moduleinfo = new \stdClass();
        $moduleinfo->modulename = 'page';
        $moduleinfo->add = 'page';
        $moduleinfo->module = $DB->get_field('modules', 'id', ['name' => 'page']);
        $moduleinfo->name = $params['name'];
        $moduleinfo->section = $params['section'];
        $moduleinfo->visible = 1;
        $moduleinfo->course = $course->id;
        $moduleinfo->content = $params['content'];
        $moduleinfo->contentformat = $params['contentformat'];
        $moduleinfo->printintro = 0;
        $moduleinfo->printlastmodified = 0;
        $moduleinfo->display = RESOURCELIB_DISPLAY_OPEN;

        $cm = add_moduleinfo($moduleinfo, $course);
        if (!$cm) {
            throw new \moodle_exception('module_create_failed', 'local_ai_course_engine');
        }

        return ['cmid' => (int)$cm->id];
    }

    public static function add_page_returns(): external_single_structure {
        return new external_single_structure([
            'cmid' => new external_value(PARAM_INT, 'The course module id of the created page'),
        ]);
    }
}