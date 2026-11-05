<?php
/**
 * Plugin Name: Bree Legends — MUME Dating Indicators
 * Description: Compact Diku and MUME epoch comparison tables. Use [mume_date_indicators] on a page.
 * Version: 0.3.0
 * Requires at least: 5.8
 * Requires PHP: 7.4
 * Author: Bree Legends
 * License: GPL-3.0-or-later
 */
if (!defined('ABSPATH')) { exit; }

function bree_mdi_data() {
    $seed = json_decode((string) file_get_contents(__DIR__ . '/public/catalogue.json'), true);
    $stored = get_option('bree_mdi_catalogue', null);
    if (!is_array($stored)) { return $seed; }
    // Older saved catalogues retain research edits while receiving the new
    // comparison layout and newly bundled rows. Existing observations win.
    $needs_comparison = !isset($stored['comparison']);
    if ($needs_comparison && isset($seed['comparison'])) { $stored['comparison'] = $seed['comparison']; }
    $seed_indicators = array_column($seed['indicators'], null, 'id');
    $ids = array();
    foreach ($stored['indicators'] as &$indicator) {
        $ids[] = $indicator['id'];
        if (!isset($indicator['comparison']) && isset($seed_indicators[$indicator['id']]['comparison'])) {
            $indicator['comparison'] = $seed_indicators[$indicator['id']]['comparison'];
        }
    }
    unset($indicator);
    $source_ids = array_column($stored['sources'], 'id');
    foreach ($seed['indicators'] as $indicator) {
        if ($needs_comparison && !in_array($indicator['id'], $ids, true)) { $stored['indicators'][] = $indicator; }
    }
    foreach ($seed['sources'] as $source) {
        if ($needs_comparison && !in_array($source['id'], $source_ids, true)) { $stored['sources'][] = $source; }
    }
    return $stored;
}

function bree_mdi_validate($data) {
    if (!is_array($data) || ($data['schema'] ?? '') !== 'mume-date-indicators/1') {
        return new WP_Error('invalid', 'Choose a MUME dating-indicator catalogue.');
    }
    foreach (array('epochs', 'sources', 'indicators') as $key) {
        if (!isset($data[$key]) || !is_array($data[$key]) || count($data[$key]) > 5000) {
            return new WP_Error('invalid', 'Missing or oversized ' . $key . ' list.');
        }
        $ids = array();
        foreach ($data[$key] as $row) {
            if (!is_array($row) || !isset($row['id']) || !is_string($row['id']) ||
                !preg_match('/\A[a-zA-Z0-9_-]{1,150}\z/', $row['id']) || isset($ids[$row['id']])) {
                return new WP_Error('invalid', 'Invalid or duplicate identity in ' . $key . '.');
            }
            $ids[$row['id']] = true;
            foreach (array('start', 'end', 'date_start', 'date_end', 'documented_date') as $field) {
                if (!empty($row[$field]) && (!is_string($row[$field]) ||
                    !preg_match('/\A\d{4}-\d{2}-\d{2}\z/', $row[$field]) ||
                    !checkdate((int) substr($row[$field], 5, 2), (int) substr($row[$field], 8, 2), (int) substr($row[$field], 0, 4)))) {
                    return new WP_Error('invalid', 'Invalid date in ' . $field . '.');
                }
            }
            if (!empty($row['date_start']) && !empty($row['date_end']) && $row['date_start'] > $row['date_end']) {
                return new WP_Error('invalid', 'A source date range is reversed.');
            }
        }
    }
    $source_ids = array_column($data['sources'], 'id');
    foreach ($data['indicators'] as $indicator) {
        if (!isset($indicator['title'], $indicator['category'], $indicator['mode'], $indicator['status'], $indicator['patterns'], $indicator['attestations']) ||
            !in_array($indicator['mode'], array('introduced_by', 'observed_by', 'transition', 'unresolved', 'lineage', 'documented'), true) ||
            !in_array($indicator['status'], array('documented', 'provisional', 'unresolved'), true) ||
            !is_array($indicator['attestations']) || !is_array($indicator['patterns'])) {
            return new WP_Error('invalid', 'An indicator has an invalid structure.');
        }
        foreach ($indicator['attestations'] as $observation) {
            if (!is_array($observation) || !isset($observation['source_id'], $observation['quote']) ||
                !in_array($observation['source_id'], $source_ids, true) || !is_string($observation['quote'])) {
                return new WP_Error('invalid', 'An observation has a missing source or quotation.');
            }
        }
    }
    return $data;
}

function bree_mdi_shortcode() {
    wp_enqueue_style('bree-mdi', plugins_url('public/style.css', __FILE__), array(), '0.3.0');
    wp_enqueue_script('bree-mdi', plugins_url('public/chronology.js', __FILE__), array(), '0.3.0', true);
    $json = wp_json_encode(bree_mdi_data(), JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT);
    return '<div class="bree-mume-dates"><script type="application/json" class="mdi-data">' . $json . '</script><div class="mdi-app"><noscript>Enable JavaScript to browse the comparison tables.</noscript></div></div>';
}
add_shortcode('mume_date_indicators', 'bree_mdi_shortcode');

function bree_mdi_menu() {
    add_management_page('MUME Dating Indicators', 'MUME Dating Indicators', 'manage_options', 'bree-mume-dates', 'bree_mdi_admin');
}
add_action('admin_menu', 'bree_mdi_menu');

function bree_mdi_admin() {
    if (!current_user_can('manage_options')) { return; }
    $data = bree_mdi_data();
    echo '<div class="wrap"><h1>MUME Dating Indicators</h1><p>Add <code>[mume_date_indicators]</code> to a normal WordPress page. The plugin does not create or publish a page automatically.</p>';
    echo '<p>Current catalogue: ' . esc_html(count($data['indicators'])) . ' indicators; updated ' . esc_html($data['updated_at']) . '.</p>';
    if (!empty($_GET['saved'])) { echo '<div class="notice notice-success"><p>The chronology has been updated.</p></div>'; }
    echo '<h2>Add dated evidence</h2><p>Adding an earlier usable observation can move an indicator’s shared sorting anchor and epoch. A source whose date depends on this same indicator cannot calibrate it.</p>';
    echo '<form method="post" action="' . esc_url(admin_url('admin-post.php')) . '">';
    wp_nonce_field('bree_mdi_add_observation');
    echo '<input type="hidden" name="action" value="bree_mdi_add_observation"><table class="form-table"><tr><th>Indicator</th><td><select name="indicator_id">';
    foreach ($data['indicators'] as $indicator) {
        echo '<option value="' . esc_attr($indicator['id']) . '">' . esc_html($indicator['title']) . '</option>';
    }
    echo '</select><p class="description">For a punctuation transition, choose whether this observation shows the older or newer form below.</p></td></tr>';
    foreach (array('source_title' => 'Source title', 'source_url' => 'Source URL (optional)', 'date_label' => 'Date as displayed / described',
                   'date_start' => 'Earliest possible source date (optional)', 'date_end' => 'Latest possible source date',
                   'file_label' => 'Source file / passage label (optional)', 'line_start' => 'First source line (optional)') as $name => $label) {
        $type = strpos($name, 'date_') === 0 && $name !== 'date_label' ? 'date' : ($name === 'source_url' ? 'url' : ($name === 'line_start' ? 'number' : 'text'));
        $required = in_array($name, array('source_title', 'date_label', 'date_end'), true) ? ' required' : '';
        echo '<tr><th><label for="mdi-' . esc_attr($name) . '">' . esc_html($label) . '</label></th><td><input class="regular-text" id="mdi-' . esc_attr($name) . '" name="' . esc_attr($name) . '" type="' . esc_attr($type) . '"' . $required . '></td></tr>';
    }
    echo '<tr><th>Confidence in source date</th><td><select name="date_confidence"><option value="high">High</option><option value="medium">Medium</option><option value="low">Low (shown, but does not move the anchor)</option></select></td></tr>';
    echo '<tr><th>Variant</th><td><select name="variant"><option value="default">Ordinary observation</option><option value="old">Older form</option><option value="new">Newer form</option></select></td></tr>';
    echo '<tr><th><label for="mdi-basis">Date evidence</label></th><td><textarea required class="large-text" rows="3" id="mdi-basis" name="date_basis" placeholder="Explain how the log date is established."></textarea></td></tr>';
    echo '<tr><th><label for="mdi-quote">Exact quotation</label></th><td><textarea required class="large-text" rows="3" id="mdi-quote" name="quote"></textarea></td></tr>';
    echo '<tr><th>Calibration</th><td><label><input type="checkbox" name="independent" value="1"> This date is supported independently of this indicator.</label><p class="description">Leave unchecked to retain the evidence without using it to move the shared anchor.</p></td></tr></table>';
    submit_button('Save evidence & update chronology');
    echo '</form><hr><h2>Replace the catalogue</h2><p>Upload an updated catalogue exported from the research workflow. A backup of the previous catalogue is retained. Saved data survives plugin updates.</p><form method="post" enctype="multipart/form-data" action="' . esc_url(admin_url('admin-post.php')) . '">';
    wp_nonce_field('bree_mdi_upload');
    echo '<input type="hidden" name="action" value="bree_mdi_upload"><input required type="file" accept=".json,application/json" name="catalogue">';
    submit_button('Upload catalogue');
    echo '</form><p><a class="button" href="' . esc_url(wp_nonce_url(admin_url('admin-post.php?action=bree_mdi_download'), 'bree_mdi_download')) . '">Download current catalogue</a></p></div>';
}

function bree_mdi_guard($nonce) {
    if (!current_user_can('manage_options')) { wp_die('Administrator access required.', '', array('response' => 403)); }
    check_admin_referer($nonce);
}
function bree_mdi_store($data) {
    $validated = bree_mdi_validate($data);
    if (is_wp_error($validated)) { wp_die(esc_html($validated->get_error_message())); }
    update_option('bree_mdi_previous_catalogue', bree_mdi_data(), false);
    update_option('bree_mdi_catalogue', $validated, false);
    wp_safe_redirect(admin_url('tools.php?page=bree-mume-dates&saved=1')); exit;
}
function bree_mdi_add_observation() {
    bree_mdi_guard('bree_mdi_add_observation');
    $data = bree_mdi_data(); $identity = sanitize_key(wp_unslash($_POST['indicator_id'] ?? ''));
    $index = array_search($identity, array_column($data['indicators'], 'id'), true);
    if ($index === false) { wp_die('Choose an existing indicator.'); }
    $sid = 'source_' . str_replace('-', '', wp_generate_uuid4());
    $line = absint($_POST['line_start'] ?? 0);
    $source = array('id' => $sid, 'title' => sanitize_text_field(wp_unslash($_POST['source_title'] ?? '')),
                    'url' => esc_url_raw(wp_unslash($_POST['source_url'] ?? ''), array('http', 'https')),
                    'date_label' => sanitize_text_field(wp_unslash($_POST['date_label'] ?? '')),
                    'date_start' => sanitize_text_field(wp_unslash($_POST['date_start'] ?? '')) ?: null,
                    'date_end' => sanitize_text_field(wp_unslash($_POST['date_end'] ?? '')),
                    'date_confidence' => sanitize_key(wp_unslash($_POST['date_confidence'] ?? 'low')),
                    'date_basis' => sanitize_textarea_field(wp_unslash($_POST['date_basis'] ?? '')),
                    'dependencies' => array(), 'calibration' => empty($_POST['independent']) ? 'unresolved' : 'independent');
    $quote = sanitize_textarea_field(wp_unslash($_POST['quote'] ?? ''));
    if (!$source['title'] || !$source['date_label'] || !$source['date_end'] || !$source['date_basis'] || !$quote) { wp_die('Complete the source, date, date evidence and quotation.'); }
    if (!in_array($source['date_confidence'], array('high', 'medium', 'low'), true)) { wp_die('Choose a date confidence.'); }
    $variant = sanitize_key(wp_unslash($_POST['variant'] ?? 'default'));
    if (!in_array($variant, array('default', 'old', 'new'), true)) { wp_die('Choose a message variant.'); }
    $data['sources'][] = $source;
    $data['indicators'][$index]['attestations'][] = array('id' => $sid . '_observation', 'source_id' => $sid,
        'quote' => $quote, 'file' => sanitize_text_field(wp_unslash($_POST['file_label'] ?? '')),
        'line_start' => $line ?: null, 'line_end' => $line ?: null, 'group' => $variant);
    $data['updated_at'] = gmdate('Y-m-d');
    $data['indicators'][$index]['history'][] = array('date' => $data['updated_at'], 'note' => 'Added dated evidence: ' . $source['title'] . '.');
    bree_mdi_store($data);
}
add_action('admin_post_bree_mdi_add_observation', 'bree_mdi_add_observation');
function bree_mdi_upload() {
    bree_mdi_guard('bree_mdi_upload');
    $file = $_FILES['catalogue'] ?? array();
    if (($file['error'] ?? 1) !== UPLOAD_ERR_OK || ($file['size'] ?? 0) > 4 * 1024 * 1024 || !is_uploaded_file($file['tmp_name'] ?? '')) { wp_die('Choose a JSON catalogue smaller than 4 MiB.'); }
    $data = json_decode((string) file_get_contents($file['tmp_name']), true);
    bree_mdi_store($data);
}
add_action('admin_post_bree_mdi_upload', 'bree_mdi_upload');
function bree_mdi_download() {
    bree_mdi_guard('bree_mdi_download');
    nocache_headers(); header('Content-Type: application/json; charset=utf-8');
    header('Content-Disposition: attachment; filename="mume-date-indicators.json"');
    echo wp_json_encode(bree_mdi_data(), JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES); exit;
}
add_action('admin_post_bree_mdi_download', 'bree_mdi_download');
