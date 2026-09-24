<?php
namespace local_ai_course_engine\external;

defined('MOODLE_INTERNAL') || die();

use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_single_structure;
use core_external\external_value;

class update_section extends external_api {
    public static function update_section_parameters(): external_function_parameters {
        return new external_function_parameters([
            'courseid' => new external_value(PARAM_INT, 'The course id'),
            'section' => new external_value(PARAM_INT, 'The zero-based section number'),
            'name' => new external_value(PARAM_TEXT, 'The section name'),
            'summary' => new external_value(PARAM_RAW, 'The section summary'),
            'summaryformat' => new external_value(
                PARAM_INT,
                'The section summary text format',
                VALUE_DEFAULT,
                FORMAT_HTML
            ),
        ]);
    }

    public static function update_section(
        int $courseid,
        int $section,
        string $name,
        string $summary,
        int $summaryformat = FORMAT_HTML
    ): array {
        global $CFG, $DB;

        $params = self::validate_parameters(
            self::update_section_parameters(),
            [
                'courseid' => $courseid,
                'section' => $section,
                'name' => $name,
                'summary' => $summary,
                'summaryformat' => $summaryformat,
            ]
        );

        require_once($CFG->dirroot . '/course/lib.php');

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
        require_capability('moodle/course:update', \context_course::instance($course->id));

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

        $sectionrecord->name = $params['name'];
        $sectionrecord->summary = $params['summary'];
        $sectionrecord->summaryformat = $params['summaryformat'];
        $DB->update_record('course_sections', $sectionrecord);
        rebuild_course_cache($course->id, true);

        return [
            'section' => (int)$sectionrecord->section,
            'name' => $sectionrecord->name,
        ];
    }

    public static function update_section_returns(): external_single_structure {
        return new external_single_structure([
            'section' => new external_value(PARAM_INT, 'The zero-based section number'),
            'name' => new external_value(PARAM_TEXT, 'The section name'),
        ]);
    }
}