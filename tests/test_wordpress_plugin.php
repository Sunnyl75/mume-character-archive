<?php
/** Standalone contract checks; WordPress services are stubbed, not integration-tested. */
define('ABSPATH', __DIR__);
$options = array();
$hooks = array();
$pages = array();
$kses_calls = 0;
function plugin_dir_path($file) { return dirname($file) . '/'; }
function register_activation_hook($file, $callback) {}
function add_action($name, $callback) { global $hooks; $hooks[$name][] = $callback; }
function add_filter($name, $callback, ...$args) { add_action($name, $callback); }
function add_shortcode(...$args) {}
function get_option($name, $fallback = false) { global $options; return $options[$name] ?? $fallback; }
function update_option($name, $value, ...$args) { global $options; $options[$name] = $value; return true; }
function delete_option($name) { global $options; unset($options[$name]); }
function get_page_by_path($slug) { global $pages; return $pages[$slug] ?? null; }
function has_shortcode($content, $name) { return str_contains($content, '[' . $name . ']'); }
function wp_insert_post($post, ...$args) { global $pages; $post['ID'] = 42; $pages[$post['post_name']] = (object) $post; return 42; }
function is_wp_error($value) { return $value instanceof WP_Error; }
// Verify the plugin delegates BOTH HTML fields to WordPress's sanitizer.
function wp_kses($value, $allowed) { global $kses_calls; ++$kses_calls; return $value; }
function get_post_status($id) { return 'publish'; }
function get_permalink($id) { return 'https://example.test/deck-of-chars/'; }
function home_url($path) { return 'https://example.test' . $path; }
function is_page() { return true; }
function get_queried_object_id() { return 42; }
function get_post_field(...$args) { return '[bree_deck_of_chars]'; }
function trailingslashit($value) { return rtrim($value, '/') . '/'; }
function plugins_url($path, ...$args) { return 'https://example.test/wp-content/plugins/bree-deck-of-chars/' . $path; }
function rest_url($path) { return 'https://example.test/wp-json/' . $path; }
function admin_url($path) { return 'https://example.test/wp-admin/' . $path; }
function esc_url($value) { return htmlspecialchars($value, ENT_QUOTES); }
function wp_json_encode($value, $flags = 0) { return json_encode($value, $flags); }
function status_header($code) {}
function nocache_headers() {}
class WP_Error { public function __construct(public $code, public $message, public $data) {} }
class WP_REST_Request {
    public function __construct(private $token) {}
    public function get_header($name) { return $this->token; }
}
function expect($condition, $message) { if (!$condition) { throw new Exception($message); } }
require $argv[1];
if (($argv[2] ?? '') === 'render') {
    $hooks['template_redirect'][0]();
    exit;
}
$data = bree_deck_default_data();
expect(count($data['characters']) > 0, 'Bundled data did not load');
expect(!is_wp_error(bree_deck_validate_data($data)), 'Exporter schema was rejected');
expect($kses_calls > 0, 'Formatted whois evidence did not pass through wp_kses');
expect(is_wp_error(bree_deck_publish_permission(new WP_REST_Request(''))), 'Missing key was accepted');
$key = str_repeat('a', 48);
update_option('bree_deck_token_hash', hash('sha256', $key));
expect(is_wp_error(bree_deck_publish_permission(new WP_REST_Request(str_repeat('b', 48)))), 'Incorrect key was accepted');
expect(bree_deck_publish_permission(new WP_REST_Request($key)) === true, 'Correct key was rejected');
delete_option('bree_deck_token_hash');
expect(is_wp_error(bree_deck_publish_permission(new WP_REST_Request($key))), 'Revoked key was accepted');
$saved = bree_deck_store_data($data);
expect(!is_wp_error($saved), 'Valid dataset was not stored');
$old = $data;
$old['portraitFiles'] = array('Unknown.png');
update_option('bree_deck_published_data', $old, false);
expect(in_array('Maia.png', bree_deck_data()['portraitFiles'], true), 'New artwork was hidden by an older published manifest');
update_option('bree_deck_published_data', $data, false);
$before = get_option('bree_deck_published_data');
$bad = $data;
$bad['characters'] = array();
expect(is_wp_error(bree_deck_store_data($bad)), 'Empty data was accepted');
expect(get_option('bree_deck_published_data') === $before, 'Failed update replaced published data');
$bad = $data;
$bad['portraitFiles'][] = '../../unsafe.png';
expect(is_wp_error(bree_deck_store_data($bad)), 'Unsafe portrait path was accepted');
$bad = $data;
$bad['characters'][] = $bad['characters'][0];
expect(is_wp_error(bree_deck_store_data($bad)), 'Duplicate character ID was accepted');
$bad = $data;
$bad['characters'][0]['id'] = 'unsafe" onclick="alert(1)';
expect(is_wp_error(bree_deck_store_data($bad)), 'Unsafe character identity was accepted');
$bad = $data;
$bad['characters'][0]['mentionCount'] = '<img src=x onerror=alert(1)>';
$safe = bree_deck_validate_data($bad);
expect($safe['characters'][0]['mentionCount'] === 0, 'Numeric display field accepted markup');
$pages['deck-of-chars'] = (object) array('ID' => 8, 'post_content' => 'Existing content');
bree_deck_activate();
expect($pages['deck-of-chars']->post_content === 'Existing content', 'Existing page was overwritten');
unset($pages['deck-of-chars']);
bree_deck_activate();
expect($pages['deck-of-chars']->post_content === '[bree_deck_of_chars]', 'Deck page was not created');
echo 'Plugin contract checks passed (' . count($data['characters']) . " bundled characters).\n";
