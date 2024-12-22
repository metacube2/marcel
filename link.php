<?php
/***************************************************************
 *  Einseiten-Anwendung (index.php) für eine Linkliste
 *  mit Login-/Logout-Funktion und einfacher JSON-Datenspeicherung.
 ***************************************************************/

// ---------------------- Konfiguration -------------------------
session_start();

// Beispiel-Nutzer (Benutzername: admin / Passwort: demo)
$USER_CREDENTIALS = [
    'admin' => 'gradio'
];

// Dateiname, in dem unsere Links gespeichert werden
$LINKS_FILE = __DIR__ . '/links.json';

// ---------------------- Funktionen ----------------------------

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

// ---------------------- Login/Logout --------------------------
if (isset($_POST['action']) && $_POST['action'] === 'login') {
    // Login-Formular wurde abgeschickt
    $username = trim($_POST['username'] ?? '');
    $password = trim($_POST['password'] ?? '');
    
    // Check Benutzername und Passwort
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
        $newTitle = trim($_POST['title'] ?? '');
        $newUrl   = trim($_POST['url'] ?? '');
        
        if ($newTitle !== '' && $newUrl !== '') {
            $links[] = [
                'title' => $newTitle,
                'url'   => $newUrl
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
        
        if ($editIndex >= 0 && isset($links[$editIndex])) {
            $links[$editIndex]['title'] = $editTitle;
            $links[$editIndex]['url']   = $editUrl;
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

// ---------------------- HTML-Ausgabe --------------------------
?>
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Amateurfunk-Linkliste</title>
    <style>
        /* -------- Reset ein wenig anpassen -------- */
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: Arial, sans-serif;
            background: #f0f7ff;
            color: #333;
            padding: 20px;
        }

        /* -------- Container und Layout -------- */
        .container {
            max-width: 600px;
            margin: 0 auto;
        }

        header, footer {
            text-align: center;
            margin-bottom: 20px;
        }

        header h1 {
            margin-bottom: 10px;
            font-size: 1.5em;
            color: #0066cc;
        }

        /* -------- Amateurfunk-Logo/Text -------- */
        header .radio-icon {
            font-size: 2em;
            color: #0066cc;
        }

        /* -------- Navigation / Login-Bereich -------- */
        .nav, .login {
            display: flex;
            justify-content: center;
            gap: 10px;
            margin-bottom: 20px;
        }

        .nav form, .login form {
            display: inline;
        }

        .nav button, .login button {
            padding: 8px 15px;
            border: none;
            border-radius: 4px;
            background-color: #0066cc;
            color: #fff;
            cursor: pointer;
        }
        .nav button:hover, .login button:hover {
            background-color: #004999;
        }

        /* -------- Linkliste -------- */
        .links-list {
            list-style: none;
            margin-bottom: 30px;
        }

        .links-list li {
            padding: 10px;
            margin-bottom: 5px;
            background: #fff;
            border: 1px solid #ddd;
            border-radius: 4px;
        }

        .links-list li a {
            text-decoration: none;
            color: #0066cc;
            word-wrap: break-word; /* Für Mobile besser bei langen URLs */
        }

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
            background: #fff;
            border: 1px solid #ddd;
            padding: 15px;
            border-radius: 4px;
        }

        .form-container h2 {
            margin-bottom: 10px;
        }

        .form-container label {
            display: block;
            margin: 10px 0 5px;
        }

        .form-container input[type="text"], 
        .form-container input[type="url"], 
        .form-container input[type="password"] {
            width: 100%;
            padding: 8px;
            border: 1px solid #bbb;
            border-radius: 4px;
        }

        .form-container .submit-button {
            background-color: #0066cc;
            color: #fff;
            padding: 10px 15px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            margin-top: 10px;
        }

        .form-container .submit-button:hover {
            background-color: #004999;
        }

        /* -------- Fehlermeldung -------- */
        .error {
            color: red;
            margin: 10px 0;
        }

        /* -------- Footer -------- */
        footer {
            margin-top: 30px;
            font-size: 0.9em;
            color: #666;
        }

        /* -------- Responsives Design -------- */
        @media (max-width: 600px) {
            body {
                padding: 10px;
            }
            .nav, .login {
                flex-direction: column;
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

    <!-- Login/Logout -->
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

                <!-- Bearbeiten-Formular (wird per Knopfdruck eingeblendet) -->
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

            <button type="submit" class="submit-button">Hinzufügen</button>
        </form>
    </div>
    <?php endif; ?>

    <footer>
        <p>© <?php echo date('Y'); ?> Amateurfunk-Linkliste.</p>
    </footer>
</div>
</body>
</html>
