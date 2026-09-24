<?php
// Web service function declarations for the local_ai_course_engine plugin.
//
// These functions fill the gap left by Moodle core web services: core
// provides no function that can set a section name/summary or create an
// activity module instance (core_course_edit_section only changes
// visibility/marker/deletion and no mod_page_* web service exists).

$functions = [
    'local_ai_course_engine_update_section' => [
        'classname' => 'local_ai_course_engine\external\update_section',
        'methodname' => 'update_section',
        'description' => 'local_ws_update_section_desc',
        'type' => 'write',
        'capabilities' => 'moodle/course:update',
    ],
    'local_ai_course_engine_add_page' => [
        'classname' => 'local_ai_course_engine\external\add_page',
        'methodname' => 'add_page',
        'description' => 'local_ws_add_page_desc',
        'type' => 'write',
        'capabilities' => 'mod/page:addinstance',
    ],
];