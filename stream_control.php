<?php
session_start();

function startEncoder() {
    exec('nohup /var/www/html/stream_konvertieren.sh > /dev/null 2>&1 & echo $!', $output);
    return $output[0];
}

function stopEncoder($pid) {
    exec("kill $pid");
}

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $action = $_POST['action'];
    
    if ($action === 'start') {
        if (!isset($_SESSION['encoder_pid'])) {
            $pid = startEncoder();
            $_SESSION['encoder_pid'] = $pid;
            echo json_encode(['status' => 'started', 'pid' => $pid]);
        } else {
            echo json_encode(['status' => 'already_running', 'pid' => $_SESSION['encoder_pid']]);
        }
    } elseif ($action === 'stop') {
        if (isset($_SESSION['encoder_pid'])) {
            stopEncoder($_SESSION['encoder_pid']);
            unset($_SESSION['encoder_pid']);
            echo json_encode(['status' => 'stopped']);
        } else {
            echo json_encode(['status' => 'not_running']);
        }
    }
}
