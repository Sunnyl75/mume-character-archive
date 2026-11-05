<?php
/**
 * Plugin Name: Bree Legends — Deck of Chars
 * Description: Illustrated MUME character archive with dashboard uploads and a data-only publishing API.
 * Version: 1.0.1
 * Requires at least: 6.2
 * Requires PHP: 8.1
 * Author: Bree Legends
 * License: GPL-3.0-or-later
 */
if (!defined('ABSPATH')) {
    exit;
}

define('BREE_DECK_DIR', plugin_dir_path(__FILE__));

function bree_deck_activate(): void {
    $existing = get_page_by_path('deck-of-chars');
    if (!$existing) {
        $id = wp_insert_post(array(
            'post_type' => 'page', 'post_status' => 'publish',
            'post_title' => 'Deck of Chars', 'post_name' => 'deck-of-chars',
            'post_content' => '[bree_deck_of_chars]',
        ), true);
        if (!is_wp_error($id)) {
            update_option('bree_deck_page_id', (int) $id, false);
        }
    } elseif (has_shortcode($existing->post_content, 'bree_deck_of_chars')) {
        update_option('bree_deck_page_id', (int) $existing->ID, false);
    }
}
register_activation_hook(__FILE__, 'bree_deck_activate');

function bree_deck_page_url(): string {
    $id = (int) get_option('bree_deck_page_id', 0);
    return $id && get_post_status($id) === 'publish' ? (string) get_permalink($id) : home_url('/deck-of-chars/');
}

function bree_deck_default_data(): array {
    $raw = (string) file_get_contents(BREE_DECK_DIR . 'public/assets/data/deck-data.js');
    $prefix = 'window.DECK_CHARS = ';
    if (strpos($raw, $prefix) !== 0) {
        return array();
    }
    $decoded = json_decode(rtrim(substr($raw, strlen($prefix)), ";\r\n "), true);
    return is_array($decoded) ? $decoded : array();
}

function bree_deck_data(): array {
    $stored = get_option('bree_deck_published_data', null);
    $data = is_array($stored) ? $stored : bree_deck_default_data();
    // Plugin updates may add portraits while retaining an older published dataset.
    // The installed files are the authoritative inventory of available artwork.
    $portraits = array();
    foreach (glob(BREE_DECK_DIR . 'public/assets/cards/*.png') ?: array() as $path) {
        $name = basename($path);
        if (preg_match('/\A[A-Z][A-Za-z0-9_-]*\.png\z/', $name)) {
            $portraits[] = $name;
        }
    }
    sort($portraits);
    $data['portraitFiles'] = $portraits;
    $data['meta']['portraitFileCount'] = count($portraits);
    return $data;
}

function bree_deck_public_ajax(): void {
    nocache_headers();
    wp_send_json(bree_deck_data());
}
add_action('wp_ajax_bree_deck_data', 'bree_deck_public_ajax');
add_action('wp_ajax_nopriv_bree_deck_data', 'bree_deck_public_ajax');

/** Validate structure and remove active markup from formatted whois evidence. */
function bree_deck_validate_data($data) {
    if (!is_array($data) || !isset($data['meta']) || !is_array($data['meta'])) {
        return new WP_Error('bree_deck_invalid', 'The file does not contain Deck data.', array('status' => 400));
    }
    foreach (array('characters', 'players', 'asciiRecords', 'portraitFiles') as $key) {
        if (!isset($data[$key]) || !is_array($data[$key]) || !array_is_list($data[$key])) {
            return new WP_Error('bree_deck_invalid', 'Missing or invalid ' . $key . ' list.', array('status' => 400));
        }
    }
    if (!count($data['characters']) || count($data['characters']) > 100000) {
        return new WP_Error('bree_deck_invalid', 'The character list is empty or too large.', array('status' => 400));
    }
    $allowed_html = array('pre' => array('class' => true, 'style' => true), 'span' => array('class' => true, 'style' => true), 'br' => array());
    foreach (array('characters' => 'whoisHtml', 'asciiRecords' => 'html', 'players' => '') as $key => $html_key) {
        $ids = array();
        foreach ($data[$key] as &$row) {
            $identity_key = array('asciiRecords' => 'characterId', 'players' => 'playerId', 'characters' => 'id')[$key];
            if (!is_array($row) || !isset($row[$identity_key]) || !is_string($row[$identity_key]) || !preg_match('/\A[\p{L}\p{N}_.-]+\z/u', $row[$identity_key]) || isset($ids[$row[$identity_key]])) {
                return new WP_Error('bree_deck_invalid', 'Invalid or duplicate identity in ' . $key . '.', array('status' => 400));
            }
            $ids[$row[$identity_key]] = true;
            if ($key === 'characters') {
                $row['mentionCount'] = max(0, (int) ($row['mentionCount'] ?? 0));
            }
            if ($html_key && isset($row[$html_key])) {
                if (!is_string($row[$html_key])) {
                    return new WP_Error('bree_deck_invalid', 'Invalid whois HTML.', array('status' => 400));
                }
                $row[$html_key] = wp_kses($row[$html_key], $allowed_html);
            }
        }
        unset($row);
    }
    foreach ($data['portraitFiles'] as $file) {
        if (!is_string($file) || !preg_match('/\A[A-Za-z0-9_-]+\.png\z/', $file)) {
            return new WP_Error('bree_deck_invalid', 'Invalid portrait filename.', array('status' => 400));
        }
    }
    $data['meta']['characterCount'] = count($data['characters']);
    $data['meta']['playerCount'] = count($data['players']);
    $data['meta']['asciiRecordCount'] = count($data['asciiRecords']);
    return $data;
}

function bree_deck_store_data($data) {
    $data = bree_deck_validate_data($data);
    if (is_wp_error($data)) {
        return $data;
    }
    // One database value is replaced only after the complete payload validates.
    $saved = update_option('bree_deck_published_data', $data, false);
    if (!$saved && get_option('bree_deck_published_data') !== $data) {
        return new WP_Error('bree_deck_save_failed', 'WordPress could not save the data.', array('status' => 500));
    }
    $status = array('characterCount' => count($data['characters']), 'updatedAt' => gmdate('c'));
    update_option('bree_deck_last_update', $status, false);
    return $status;
}

function bree_deck_publish_permission(WP_REST_Request $request) {
    $token = (string) $request->get_header('X-Bree-Deck-Token');
    $expected = (string) get_option('bree_deck_token_hash', '');
    if (!$expected || strlen($token) < 32 || strlen($token) > 128 || !hash_equals($expected, hash('sha256', $token))) {
        return new WP_Error('bree_deck_forbidden', 'A valid Deck publishing key is required.', array('status' => 403));
    }
    return true;
}

add_action('rest_api_init', function (): void {
    register_rest_route('bree-deck/v1', '/data', array(
        array('methods' => 'GET', 'permission_callback' => '__return_true', 'callback' => function () {
            $response = new WP_REST_Response(bree_deck_data());
            $response->header('Cache-Control', 'no-store, max-age=0');
            return $response;
        }),
        array('methods' => 'POST', 'permission_callback' => 'bree_deck_publish_permission', 'callback' => function (WP_REST_Request $request) {
            if (strlen($request->get_body()) > 12 * 1024 * 1024) {
                return new WP_Error('bree_deck_too_large', 'Deck data exceeds 12 MiB.', array('status' => 413));
            }
            return bree_deck_store_data($request->get_json_params());
        }),
    ));
    register_rest_route('bree-deck/v1', '/status', array(
        'methods' => 'GET', 'permission_callback' => 'bree_deck_publish_permission',
        'callback' => function () { return array('ready' => true, 'lastUpdate' => get_option('bree_deck_last_update', null)); },
    ));
});

add_shortcode('bree_deck_of_chars', function (): string {
    return '<p><a href="' . esc_url(bree_deck_page_url()) . '">Open the Deck of Chars</a></p>';
});

/** Serve the existing full Deck design at a normal WordPress page URL. */
add_action('template_redirect', function (): void {
    if (!is_page() || !has_shortcode((string) get_post_field('post_content', get_queried_object_id()), 'bree_deck_of_chars')) {
        return;
    }
    $base = trailingslashit(plugins_url('public', __FILE__));
    $html = (string) file_get_contents(BREE_DECK_DIR . 'public/index.html');
    $html = preg_replace_callback('/(src|href)="((?:assets\/|bree-theme\.css|deck-of-chars\.(?:css|js))[^" ]*)"/', function ($match) use ($base) {
        return $match[1] . '="' . esc_url($base . $match[2]) . '"';
    }, $html);
    $settings = '<script>window.BREE_DECK_CONFIG=' . wp_json_encode(array(
        'dataUrl' => rest_url('bree-deck/v1/data'),
        'fallbackDataUrl' => admin_url('admin-ajax.php?action=bree_deck_data'),
        'scriptUrl' => $base . 'deck-of-chars.js',
    ), JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT) . ';window.BREE_DECK_ASSET_BASE='
        . wp_json_encode($base . 'assets/cards/', JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT) . ';</script>';
    $html = preg_replace('/<script src="[^" ]*assets\/data\/deck-data\.js"><\/script>\s*<script src="[^" ]*deck-of-chars\.js"><\/script>/',
        $settings . '<script src="' . esc_url(plugins_url('data-loader.js', __FILE__)) . '"></script>', $html);
    status_header(200);
    nocache_headers();
    header('Content-Type: text/html; charset=UTF-8');
    echo $html; // Trusted bundled template; dynamic URLs are escaped above.
    exit;
});

/** Add the destination to the primary menu without changing stored menu items. */
add_filter('wp_nav_menu_items', function (string $items, $args): string {
    if (($args->theme_location ?? '') !== 'primary' || strpos($items, '/deck-of-chars') !== false) {
        return $items;
    }
    return $items . '<li class="menu-item"><a href="' . esc_url(bree_deck_page_url()) . '">Deck of Chars</a></li>';
}, 20, 2);

/** Admin controls: manual JSON upload and a revocable data-only publishing key. */
add_action('admin_menu', function (): void {
    add_management_page('Deck of Chars', 'Deck of Chars', 'manage_options', 'bree-deck', 'bree_deck_admin');
});

function bree_deck_admin(): void {
    if (!current_user_can('manage_options')) {
        return;
    }
    $message = '';
    $new_token = '';
    if ($_SERVER['REQUEST_METHOD'] === 'POST') {
        check_admin_referer('bree_deck_manage');
        $action = sanitize_key($_POST['bree_deck_action'] ?? '');
        if ($action === 'key') {
            $new_token = wp_generate_password(48, false, false);
            update_option('bree_deck_token_hash', hash('sha256', $new_token), false);
            $message = 'Publishing key created. Copy it now; only its hash is stored. Creating a new key disables the previous key.';
        } elseif ($action === 'revoke') {
            delete_option('bree_deck_token_hash');
            $message = 'Remote publishing disabled. Your current Deck data is unchanged.';
        } elseif ($action === 'upload') {
            $file = $_FILES['bree_deck_file'] ?? array();
            if (($file['error'] ?? UPLOAD_ERR_NO_FILE) !== UPLOAD_ERR_OK || !is_uploaded_file($file['tmp_name']) || filesize($file['tmp_name']) > 12 * 1024 * 1024) {
                $message = 'Choose a Deck JSON export under 12 MiB.';
            } else {
                $result = bree_deck_store_data(json_decode((string) file_get_contents($file['tmp_name']), true));
                $message = is_wp_error($result) ? $result->get_error_message() : 'Published ' . $result['characterCount'] . ' characters.';
            }
        }
    }
    $status = get_option('bree_deck_last_update', null);
    ?>
    <div class="wrap"><h1>Deck of Chars</h1>
    <?php if ($message) : ?><div class="notice notice-info"><p><?php echo esc_html($message); ?></p></div><?php endif; ?>
    <p><a class="button" href="<?php echo esc_url(bree_deck_page_url()); ?>">View Deck of Chars</a></p>
    <p><?php echo esc_html($status ? 'Last update: ' . $status['updatedAt'] . ' — ' . $status['characterCount'] . ' characters.' : 'Using the character data bundled with this plugin.'); ?></p>
    <?php if (!get_option('bree_deck_page_id')) : ?><p>The /deck-of-chars/ page already existed. Add <code>[bree_deck_of_chars]</code> to that page to display the Deck. Its existing content has been preserved.</p><?php endif; ?>
    <h2>Publish a rebuilt archive</h2><p>Upload the <code>deck-data.json</code> produced by the rebuild command.</p>
    <form method="post" enctype="multipart/form-data"><?php wp_nonce_field('bree_deck_manage'); ?>
    <input type="hidden" name="bree_deck_action" value="upload"><input type="file" name="bree_deck_file" accept=".json,application/json" required>
    <?php submit_button('Upload character data'); ?></form>
    <h2>Automatic publishing</h2><p>A publishing key allows your Mac to update Deck data only. Keep it private. You can disable it below.</p>
    <p>Site address: <code><?php echo esc_html(home_url('/')); ?></code></p>
    <?php if ($new_token) : ?><p><label>Copy this key: <input type="text" readonly autocomplete="off" style="width:36em;max-width:100%" value="<?php echo esc_attr($new_token); ?>"></label></p><?php endif; ?>
    <form method="post"><?php wp_nonce_field('bree_deck_manage'); ?><input type="hidden" name="bree_deck_action" value="key"><?php submit_button('Create publishing key', 'secondary'); ?></form>
    <form method="post"><?php wp_nonce_field('bree_deck_manage'); ?><input type="hidden" name="bree_deck_action" value="revoke"><?php submit_button('Disable remote publishing', 'secondary'); ?></form>
    </div>
    <?php
}
