<?php
/***************************************************************
 *  Einseiten-Anwendung (index.php) für eine Linkliste
 *  mit Login-/Logout-Funktion, einfacher JSON-Datenspeicherung
 *  und optionalem Vorschaubild pro Link (mit YouTube-Icon).
 ***************************************************************/

session_start();

// ---------------------- Konfiguration -------------------------
// Beispiel-Nutzer (Benutzername: admin / Passwort: gradio)
$USER_CREDENTIALS = [
    'admin' => 'gradio'
];

// Dateiname, in dem unsere Links gespeichert werden
$LINKS_FILE = __DIR__ . '/links.json';

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

// Link hinzufügen/bearbeiten/löschen nur, wenn eingeloggt
if (isLoggedIn()) {
    
    // Link hinzufügen
    if (isset($_POST['action']) && $_POST['action'] === 'add_link') {
        $newTitle   = trim($_POST['title'] ?? '');
        $newUrl     = trim($_POST['url'] ?? '');
        $newImgUrl  = trim($_POST['image'] ?? ''); // Bild-URL (optional)

        if ($newTitle !== '' && $newUrl !== '') {
            $links[] = [
                'title' => $newTitle,
                'url'   => $newUrl,
                'image' => $newImgUrl
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
            $links[$editIndex]['title'] = $editTitle;
            $links[$editIndex]['url']   = $editUrl;
            $links[$editIndex]['image'] = $editImg;
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
}
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

        /* -------- Körperhintergrund (Beispiel) -------- */
        body {
            font-family: Arial, sans-serif;
            /* Beispiel mit Farbverlauf: 
            background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
            */
            /* Oder mit Bild (z. B. ein Funkgerät, Antenne etc.):
               Bitte Pfad/URL anpassen! */
            background: url('https://via.placeholder.com/1200x800/404040/FFFFFF?text=-') 
                        no-repeat center center fixed;
            background-size: cover;

            color: #f0f0f0;
            padding: 20px;
        }

        .container {
            max-width: 700px;
            margin: 0 auto;
            background-color: rgba(0, 0, 0, 0.65); /* dunkle Transparenz, damit Schrift lesbar bleibt */
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
            flex-wrap: wrap; /* Für mobiles Umfließen */
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
            margin-left: 10px; /* etwas Abstand zum Text */
        }

        .links-list a {
            text-decoration: none;
            color: #66c2ff;
            font-weight: bold;
            word-wrap: break-word;
        }

        /* -------- Buttons zum Bearbeiten/Löschen -------- */
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
            .links-list li {
                flex-direction: column;
                align-items: flex-start;
            }
            .links-list .thumbnail {
                margin: 10px 0 0 0;
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

    <!-- Linkliste anzeigen -->
    <ul class="links-list">
        <?php foreach ($links as $index => $link): ?>
            <li>
                <div>
                    <a href="<?php echo htmlspecialchars($link['url']); ?>" target="_blank">
                        <?php echo htmlspecialchars($link['title']); ?>
                    </a>
                    <?php if (isLoggedIn()) : ?>
                        <div class="admin-buttons">
                            <!-- Edit Button -->
                            <button onclick="document.getElementById('editForm<?php echo $index; ?>').style.display='block'">
                                Bearbeiten
                            </button>
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
                            // YouTube-Icon verwenden (hier beispielhaft Logo von Wikipedia)
                            // Du kannst auch eine andere URL oder ein eigenes Icon nehmen
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
        <p>© <?php echo date('Y'); ?> Amateurfunk-Linkliste </p>
    </footer>
</div>
</body>
</html>
