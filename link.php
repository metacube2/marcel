<?php
/***************************************************************
 *  Einseiten-Anwendung (index.php) für eine Linkliste
 *  mit folgenden Features:
 *
 *  - Login/Logout (User admin, PW gradio)
 *  - JSON-Datenspeicherung
 *  - Suchfunktion
 *  - Klickzähler (Links)
 *  - Favoriten (Toggle)
 *  - Voting-System (Up-/Downvote -> Score)
 *  - Optionales Vorschaubild (YouTube-Icon bei youtube.com)
 *  - Optionales Hintergrundbild (konfigurierbar)
 ***************************************************************/

session_start();

// ---------------------- Konfiguration -------------------------
// Beispiel-Nutzer (Benutzername: admin / Passwort: gradio)
$USER_CREDENTIALS = [
    'admin' => 'gradio'
];

// Dateiname, in dem unsere Links gespeichert werden
$LINKS_FILE = __DIR__ . '/links.json';

// Optionales Hintergrundbild (leer lassen, falls kein Hintergrundbild)
$BACKGROUND_IMAGE = ""; 
// Beispiel: $BACKGROUND_IMAGE = "https://via.placeholder.com/1200x800/404040/FFFFFF?text=Background";

// ---------------------- Hilfsfunktionen -----------------------
/**
 * Lädt die Linkliste aus dem JSON-File
 *
 * @return array
 */
function loadLinks($file)
{
    if (!file_exists($file)) {
        return [];
    }
    $jsonData = file_get_contents($file);
    return json_decode($jsonData, true) ?? [];
}

/**
 * Schreibt die Linkliste in das JSON-File
 *
 * @param array $linksArray
 * @param string $file
 */
function saveLinks($linksArray, $file)
{
    file_put_contents($file, json_encode($linksArray, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));
}

/**
 * Prüft, ob ein Nutzer eingeloggt ist.
 *
 * @return bool
 */
function isLoggedIn()
{
    return isset($_SESSION['username']);
}

// ---------------------- Login/Logout-Prozess ------------------
if (isset($_POST['action']) && $_POST['action'] === 'login') {
    // Login-Formular wurde abgeschickt
    $username = trim($_POST['username'] ?? '');
    $password = trim($_POST['password'] ?? '');
    
    global $USER_CREDENTIALS;
    if (array_key_exists($username, $USER_CREDENTIALS) && 
        $USER_CREDENTIALS[$username] === $password
    ) {
        $_SESSION['username'] = $username;
    } else {
        $loginError = 'Falscher Benutzername oder Passwort!';
    }
} elseif (isset($_POST['action']) && $_POST['action'] === 'logout') {
    // Logout
    session_destroy();
    header("Location: {$_SERVER['PHP_SELF']}");
    exit;
}

// ---------------------- Link-Management -----------------------
$links = loadLinks($LINKS_FILE);

// Falls wir per GET "go" einen Link aufrufen, Klickzähler erhöhen und weiterleiten
if (isset($_GET['go'])) {
    $goIndex = intval($_GET['go']);
    if (isset($links[$goIndex])) {
        // Klickzähler um 1 erhöhen
        $links[$goIndex]['clicks'] = ($links[$goIndex]['clicks'] ?? 0) + 1;
        saveLinks($links, $LINKS_FILE);

        // Weiterleitung zum tatsächlichen Ziel
        header("Location: " . $links[$goIndex]['url']);
        exit;
    }
}

// Link hinzufügen/bearbeiten/löschen/favorisieren/voten nur, wenn eingeloggt
if (isLoggedIn()) {

    // Link hinzufügen
    if (isset($_POST['action']) && $_POST['action'] === 'add_link') {
        $newTitle   = trim($_POST['title'] ?? '');
        $newUrl     = trim($_POST['url'] ?? '');
        $newImgUrl  = trim($_POST['image'] ?? '');

        if ($newTitle !== '' && $newUrl !== '') {
            $links[] = [
                'title'    => $newTitle,
                'url'      => $newUrl,
                'image'    => $newImgUrl,
                'clicks'   => 0,
                'favorite' => false,
                'score'    => 0  // neu fürs Voting
            ];
            saveLinks($links, $LINKS_FILE);
            header("Location: {$_SERVER['PHP_SELF']}");
            exit;
        }
    }

    // Link bearbeiten
    if (isset($_POST['action']) && $_POST['action'] === 'edit_link') {
        $editIndex = intval($_POST['index'] ?? -1);
        $editTitle = trim($_POST['title'] ?? '');
        $editUrl   = trim($_POST['url'] ?? '');
        $editImg   = trim($_POST['image'] ?? '');

        if ($editIndex >= 0 && isset($links[$editIndex])) {
            $links[$editIndex]['title']    = $editTitle;
            $links[$editIndex]['url']      = $editUrl;
            $links[$editIndex]['image']    = $editImg;
            // Sicherstellen, dass Klickzähler, Favoriten, Score ex. sind
            $links[$editIndex]['clicks']   = $links[$editIndex]['clicks'] ?? 0;
            $links[$editIndex]['favorite'] = $links[$editIndex]['favorite'] ?? false;
            $links[$editIndex]['score']    = $links[$editIndex]['score'] ?? 0;

            saveLinks($links, $LINKS_FILE);
            header("Location: {$_SERVER['PHP_SELF']}");
            exit;
        }
    }

    // Link löschen
    if (isset($_POST['action']) && $_POST['action'] === 'delete_link') {
        $deleteIndex = intval($_POST['index'] ?? -1);
        
        if ($deleteIndex >= 0 && isset($links[$deleteIndex])) {
            array_splice($links, $deleteIndex, 1);
            saveLinks($links, $LINKS_FILE);
            header("Location: {$_SERVER['PHP_SELF']}");
            exit;
        }
    }

    // Favorit toggeln
    if (isset($_POST['action']) && $_POST['action'] === 'toggle_fav') {
        $favIndex = intval($_POST['index'] ?? -1);
        if ($favIndex >= 0 && isset($links[$favIndex])) {
            $isFav = $links[$favIndex]['favorite'] ?? false;
            $links[$favIndex]['favorite'] = !$isFav;
            saveLinks($links, $LINKS_FILE);
            header("Location: {$_SERVER['PHP_SELF']}");
            exit;
        }
    }

    // Voting Up/Down
    if (isset($_POST['action']) && in_array($_POST['action'], ['vote_up', 'vote_down'])) {
        $voteIndex = intval($_POST['index'] ?? -1);
        if ($voteIndex >= 0 && isset($links[$voteIndex])) {
            $links[$voteIndex]['score'] = $links[$voteIndex]['score'] ?? 0;
            if ($_POST['action'] === 'vote_up') {
                $links[$voteIndex]['score']++;
            } else {
                $links[$voteIndex]['score']--;
            }
            saveLinks($links, $LINKS_FILE);
            header("Location: {$_SERVER['PHP_SELF']}");
            exit;
        }
    }
}

// ---------------------- Suchfunktion (für alle User) ----------
$searchQuery = trim($_GET['search'] ?? '');

// Links filtern (Titel oder URL enthalten den Suchbegriff)
$filteredLinks = array_filter($links, function($link) use ($searchQuery) {
    if ($searchQuery === '') return true; // Nichts gesucht -> Alle Links
    return (stripos($link['title'], $searchQuery) !== false || 
            stripos($link['url'],   $searchQuery) !== false);
});
?>
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Amateurfunk-Linkliste</title>
    <style>
        /* -------- Reset -------- */
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        /* -------- Hintergrundbild optional -------- */
        <?php if (!empty($BACKGROUND_IMAGE)): ?>
        body {
            font-family: Arial, sans-serif;
            background: url('<?php echo $BACKGROUND_IMAGE; ?>')
                        no-repeat center center fixed;
            background-size: cover;
            color: #f0f0f0;
            padding: 20px;
        }
        <?php else: ?>
        body {
            font-family: Arial, sans-serif;
            background: #303030; /* Einfacher Hintergrund */
            color: #f0f0f0;
            padding: 20px;
        }
        <?php endif; ?>

        .container {
            max-width: 700px;
            margin: 0 auto;
            background-color: rgba(0, 0, 0, 0.65); 
            padding: 20px;
            border-radius: 10px;
        }

        header, footer {
            text-align: center;
            margin-bottom: 20px;
        }

        header h1 {
            margin-bottom: 10px;
            font-size: 1.6em;
            color: #66c2ff;
        }

        /* -------- Amateurfunk-Logo/Text -------- */
        header .radio-icon {
            font-size: 2.2em;
            color: #66c2ff;
            margin-bottom: 10px;
        }

        /* -------- Login/Logout-Bereich -------- */
        .login, .nav {
            display: flex;
            justify-content: center;
            gap: 10px;
            margin-bottom: 20px;
        }

        .login form, .nav form {
            display: inline;
        }

        .login button, .nav button {
            padding: 8px 15px;
            border: none;
            border-radius: 4px;
            background-color: #66c2ff;
            color: #333;
            cursor: pointer;
        }
        .login button:hover, .nav button:hover {
            background-color: #3399ff;
        }

        /* -------- Fehlermeldung -------- */
        .error {
            color: #ffaaaa;
            text-align: center;
            margin-bottom: 10px;
        }

        /* -------- Suchformular -------- */
        .search-form {
            text-align: center;
            margin-bottom: 20px;
        }
        .search-form input[type="text"] {
            width: 70%;
            padding: 8px;
            border-radius: 4px;
            border: 1px solid #ccc;
            margin-right: 8px;
        }
        .search-form button {
            padding: 8px 15px;
            border: none;
            border-radius: 4px;
            background-color: #66c2ff;
            color: #333;
            cursor: pointer;
        }
        .search-form button:hover {
            background-color: #3399ff;
        }

        /* -------- Linkliste und einzelner Link-Eintrag -------- */
        .links-list {
            list-style: none;
            margin-bottom: 30px;
        }

        .links-list li {
            background-color: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255,255,255,0.2);
            border-radius: 6px;
            padding: 10px;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            flex-wrap: wrap;
            position: relative;
        }

        /* -------- Favoritenstern ---------- */
        .favorite-star {
            position: absolute;
            top: 10px;
            right: 10px;
            font-size: 1.3em;
            color: gold;
        }
        .favorite-star.hidden {
            display: none;
        }

        /* -------- Voting-Bereich (Up/Down) -------- */
        .voting-container {
            margin-right: 15px;
            text-align: center;
        }
        .voting-container form {
            margin: 5px 0;
        }
        .voting-button {
            background-color: #66c2ff;
            color: #333;
            border: none;
            border-radius: 4px;
            padding: 4px 8px;
            cursor: pointer;
        }
        .voting-button:hover {
            background-color: #3399ff;
        }
        .score-display {
            font-size: 1.1em;
            font-weight: bold;
            color: #ffcc00;
        }

        /* -------- Vorschaubild rechts neben dem Text -------- */
        .links-list .thumbnail {
            width: 60px;
            height: 60px;
            object-fit: cover; 
            border: 2px solid #66c2ff;
            border-radius: 8px;
            margin-left: auto; 
            margin-right: 0;
            margin-left: 10px; 
        }

        .links-list a {
            text-decoration: none;
            color: #66c2ff;
            font-weight: bold;
            word-wrap: break-word;
        }

        /* -------- Buttons zum Bearbeiten/Löschen/Favorisieren -------- */
        .admin-buttons {
            margin-top: 5px;
        }
        .admin-buttons form {
            display: inline;
        }
        .admin-buttons button {
            background-color: #ff6600;
            padding: 5px 8px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            color: #fff;
            margin-right: 5px;
        }
        .admin-buttons button:hover {
            background-color: #d45500;
        }

        /* -------- Formulare (Hinzufügen/Bearbeiten) -------- */
        .form-container {
            margin-bottom: 20px;
            background-color: rgba(255,255,255,0.1);
            border: 1px solid rgba(255,255,255,0.2);
            padding: 15px;
            border-radius: 6px;
        }
        .form-container h2 {
            margin-bottom: 10px;
            color: #66c2ff;
        }
        .form-container label {
            display: block;
            margin: 8px 0 4px;
            color: #f0f0f0;
        }
        .form-container input[type="text"], 
        .form-container input[type="url"], 
        .form-container input[type="password"] {
            width: 100%;
            padding: 8px;
            border: 1px solid #bbb;
            border-radius: 4px;
            margin-bottom: 10px;
        }
        .form-container .submit-button {
            background-color: #66c2ff;
            color: #333;
            padding: 10px 15px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            margin-top: 10px;
        }
        .form-container .submit-button:hover {
            background-color: #3399ff;
        }

        footer {
            margin-top: 30px;
            font-size: 0.9em;
            color: #ccc;
        }

        /* -------- Responsives Design -------- */
        @media (max-width: 600px) {
            body {
                padding: 10px;
            }
            .login, .nav {
                flex-direction: column;
            }
            .search-form input[type="text"] {
                width: 100%;
                margin-bottom: 10px;
            }
            .links-list li {
                flex-direction: column;
                align-items: flex-start;
                position: relative;
            }
            .links-list .thumbnail {
                margin: 10px 0 0 0;
            }
            .voting-container {
                margin-right: 0;
                margin-bottom: 10px;
            }
        }
    </style>
</head>
<body>
<div class="container">
    <header>
        <div class="radio-icon">📻</div>
        <h1>Amateurfunk-Linkliste</h1>
    </header>

    <!-- Login/Logout-Bereich -->
    <?php if (!isLoggedIn()) : ?>
        <div class="login">
            <form method="post" action="<?php echo $_SERVER['PHP_SELF']; ?>">
                <?php if (!empty($loginError)): ?>
                    <div class="error"><?php echo $loginError; ?></div>
                <?php endif; ?>
                <input type="hidden" name="action" value="login">
                
                <label for="username">Benutzername</label>
                <input type="text" name="username" id="username" required>

                <label for="password">Passwort</label>
                <input type="password" name="password" id="password" required>

                <button type="submit">Login</button>
            </form>
        </div>
    <?php else : ?>
        <div class="nav">
            <form method="post" action="<?php echo $_SERVER['PHP_SELF']; ?>">
                <input type="hidden" name="action" value="logout">
                <button type="submit">Logout (<?php echo htmlspecialchars($_SESSION['username']); ?>)</button>
            </form>
        </div>
    <?php endif; ?>

    <!-- Suchformular (für alle Benutzer) -->
    <div class="search-form">
        <form method="get" action="<?php echo $_SERVER['PHP_SELF']; ?>">
            <input type="text" name="search" placeholder="Links durchsuchen..." value="<?php echo htmlspecialchars($searchQuery); ?>">
            <button type="submit">Suchen</button>
        </form>
    </div>

    <!-- Linkliste anzeigen (gefiltert nach Suchbegriff) -->
    <ul class="links-list">
        <?php foreach ($filteredLinks as $index => $link): ?>
            <li>
                <!-- Favoriten-Stern (falls Link als Favorit markiert ist) -->
                <div class="favorite-star <?php echo empty($link['favorite']) ? 'hidden' : ''; ?>">★</div>
                
                <!-- VOTING: Up/Down + Score -->
                <?php if (isLoggedIn()): ?>
                    <div class="voting-container">
                        <!-- Score anzeigen -->
                        <div class="score-display">
                            <?php echo (int)($link['score'] ?? 0); ?>
                        </div>
                        <!-- Upvote-Form -->
                        <form method="post" action="<?php echo $_SERVER['PHP_SELF']; ?>">
                            <input type="hidden" name="action" value="vote_up">
                            <input type="hidden" name="index" value="<?php echo $index; ?>">
                            <button class="voting-button" type="submit">▲</button>
                        </form>
                        <!-- Downvote-Form -->
                        <form method="post" action="<?php echo $_SERVER['PHP_SELF']; ?>">
                            <input type="hidden" name="action" value="vote_down">
                            <input type="hidden" name="index" value="<?php echo $index; ?>">
                            <button class="voting-button" type="submit">▼</button>
                        </form>
                    </div>
                <?php else: ?>
                    <!-- Score-Anzeige für nicht eingeloggte Nutzer (ohne Voting-Buttons) -->
                    <div class="voting-container">
                        <div class="score-display">
                            <?php echo (int)($link['score'] ?? 0); ?>
                        </div>
                    </div>
                <?php endif; ?>

                <div>
                    <!-- Der eigentliche Link geht nicht direkt auf die URL, sondern mit ?go=INDEX zum Klickzählen -->
                    <a href="?go=<?php echo $index; ?>" target="_blank">
                        <?php echo htmlspecialchars($link['title']); ?>
                    </a>
                    
                    <!-- Aufruf-Anzeige -->
                    <p style="margin-top:5px; font-size:0.9em; color:#ccc;">
                        Aufrufe: <?php echo (int)($link['clicks'] ?? 0); ?>
                    </p>

                    <?php if (isLoggedIn()) : ?>
                        <div class="admin-buttons">
                            <!-- Edit Button -->
                            <button onclick="document.getElementById('editForm<?php echo $index; ?>').style.display='block'">
                                Bearbeiten
                            </button>
                            <!-- Toggle Favorite -->
                            <form method="post" action="<?php echo $_SERVER['PHP_SELF']; ?>" style="display:inline;">
                                <input type="hidden" name="action" value="toggle_fav">
                                <input type="hidden" name="index" value="<?php echo $index; ?>">
                                <button type="submit">
                                    <?php echo empty($link['favorite']) ? 'Favorisieren' : 'Un-Fav'; ?>
                                </button>
                            </form>
                            <!-- Delete Form -->
                            <form method="post" action="<?php echo $_SERVER['PHP_SELF']; ?>" style="display:inline;">
                                <input type="hidden" name="action" value="delete_link">
                                <input type="hidden" name="index" value="<?php echo $index; ?>">
                                <button type="submit" onclick="return confirm('Diesen Link wirklich löschen?');">
                                    Löschen
                                </button>
                            </form>
                        </div>
                    <?php endif; ?>
                </div>

                <!-- Bildanzeige (entweder benutzerdefiniertes Bild oder YouTube-Icon) -->
                <?php
                    $imgSrc = trim($link['image'] ?? '');
                    
                    // Falls kein eigenes Bild vorhanden, prüfen, ob es sich um eine YouTube-URL handelt
                    if (empty($imgSrc)) {
                        $host = parse_url($link['url'], PHP_URL_HOST) ?: '';
                        if (strpos($host, 'youtube.com') !== false || strpos($host, 'youtu.be') !== false) {
                            // YouTube-Icon verwenden (z.B. SVG von Wikipedia)
                            $imgSrc = 'https://upload.wikimedia.org/wikipedia/commons/7/75/YouTube_social_white_squircle_%282017%29.svg';
                        }
                    }
                ?>

                <?php if (!empty($imgSrc)): ?>
                    <img class="thumbnail" 
                         src="<?php echo htmlspecialchars($imgSrc); ?>" 
                         alt="Preview">
                <?php endif; ?>

                <!-- Bearbeiten-Formular (wird per Knopfdruck eingeblendet) -->
                <?php if (isLoggedIn()) : ?>
                <div class="form-container" id="editForm<?php echo $index; ?>" style="display:none;">
                    <h2>Link bearbeiten</h2>
                    <form method="post" action="<?php echo $_SERVER['PHP_SELF']; ?>">
                        <input type="hidden" name="action" value="edit_link">
                        <input type="hidden" name="index" value="<?php echo $index; ?>">
                        
                        <label for="editTitle<?php echo $index; ?>">Titel</label>
                        <input type="text" 
                               name="title" 
                               id="editTitle<?php echo $index; ?>" 
                               value="<?php echo htmlspecialchars($link['title']); ?>" 
                               required>
                        
                        <label for="editUrl<?php echo $index; ?>">URL</label>
                        <input type="url" 
                               name="url" 
                               id="editUrl<?php echo $index; ?>" 
                               value="<?php echo htmlspecialchars($link['url']); ?>" 
                               required>

                        <label for="editImg<?php echo $index; ?>">Bild-URL</label>
                        <input type="url" 
                               name="image"
                               id="editImg<?php echo $index; ?>"
                               value="<?php echo htmlspecialchars($link['image']); ?>">

                        <button type="submit" class="submit-button">Speichern</button>
                    </form>
                </div>
                <?php endif; ?>
            </li>
        <?php endforeach; ?>
    </ul>

    <!-- Formular zum Link hinzufügen (nur für eingeloggte Nutzer) -->
    <?php if (isLoggedIn()) : ?>
    <div class="form-container">
        <h2>Neuen Link hinzufügen</h2>
        <form method="post" action="<?php echo $_SERVER['PHP_SELF']; ?>">
            <input type="hidden" name="action" value="add_link">

            <label for="newTitle">Titel</label>
            <input type="text" name="title" id="newTitle" required>

            <label for="newUrl">URL</label>
            <input type="url" name="url" id="newUrl" required>

            <label for="newImg">Bild-URL (optional)</label>
            <input type="url" name="image" id="newImg" placeholder="https://...">

            <button type="submit" class="submit-button">Hinzufügen</button>
        </form>
    </div>
    <?php endif; ?>

    <footer>
        <p>© 2024 Amateurfunk-Linkliste</p>
    </footer>
</div>
</body>
</html>
