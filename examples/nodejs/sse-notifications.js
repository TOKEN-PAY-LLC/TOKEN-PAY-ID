'use strict';

/**
 * TOKEN PAY ID — Node.js SSE Notification Listener Example
 *
 * Demonstrates how to listen for real-time push notifications
 * via Server-Sent Events (SSE) stream.
 *
 * Install: npm install eventsource
 * Run:     TPID_TOKEN=eyJ... node sse-notifications.js
 */

const EventSource = require('eventsource');

const BASE_URL = 'https://tokenpay.space';
const JWT_TOKEN = process.env.TPID_TOKEN;

if (!JWT_TOKEN) {
    console.error('Set TPID_TOKEN env var with a valid JWT access token');
    process.exit(1);
}

// Connect to SSE stream with JWT token as query parameter
const url = `${BASE_URL}/api/v1/notifications/stream?token=${JWT_TOKEN}`;
const es = new EventSource(url);

es.addEventListener('notification', (event) => {
    const data = JSON.parse(event.data);
    console.log(`[NOTIFICATION] ${data.title}: ${data.body}`);
    console.log(`  Type: ${data.type}, ID: ${data.id}`);
});

es.addEventListener('ping', () => {
    // Keep-alive, ignore
});

es.onopen = () => {
    console.log('Connected to notification stream');
};

es.onerror = (err) => {
    console.error('SSE error:', err.message || 'connection lost');
    // EventSource will auto-reconnect
};

console.log('Listening for notifications... (Ctrl+C to stop)');
