// TOKEN PAY ID — Go Webhook Handler Example
// Run: go run webhook_handler.go
package main

import (
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"

	tpid "github.com/TOKEN-PAY-LLC/TOKEN-PAY-ID/sdk/go"
)

func main() {
	secret := os.Getenv("TPID_WEBHOOK_SECRET")
	if secret == "" {
		log.Fatal("Set TPID_WEBHOOK_SECRET env var")
	}

	http.HandleFunc("/webhook", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "Method not allowed", 405)
			return
		}

		signature := r.Header.Get("X-TPID-Signature")
		body, err := io.ReadAll(r.Body)
		if err != nil {
			http.Error(w, "Failed to read body", 400)
			return
		}
		payload := string(body)

		if signature == "" {
			http.Error(w, `{"error":"Missing signature"}`, 400)
			return
		}

		// Verify signature (HMAC-SHA256, Stripe-style)
		if !tpid.VerifyWebhookSignature(payload, signature, secret, 300) {
			log.Println("[WEBHOOK] Invalid signature")
			http.Error(w, `{"error":"Invalid signature"}`, 401)
			return
		}

		// Parse event
		var event struct {
			ID    string                 `json:"id"`
			Event string                 `json:"event"`
			Data  map[string]interface{} `json:"data"`
		}
		if err := json.Unmarshal(body, &event); err != nil {
			http.Error(w, `{"error":"Invalid JSON"}`, 400)
			return
		}

		log.Printf("[WEBHOOK] %s — delivery: %s\n", event.Event, event.ID)

		switch event.Event {
		case "user.oauth_connect":
			fmt.Printf("  User connected: %v\n", event.Data["email"])
		case "user.unlink":
			fmt.Printf("  User disconnected: %v\n", event.Data["user_id"])
		case "key.created":
			fmt.Printf("  API key created: %v\n", event.Data["key_name"])
		case "key.revoked":
			fmt.Printf("  API key revoked: %v\n", event.Data["key_id"])
		default:
			fmt.Printf("  Unhandled event: %s\n", event.Event)
		}

		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"received":true}`))
	})

	fmt.Println("Webhook handler running at http://localhost:4000/webhook")
	log.Fatal(http.ListenAndServe(":4000", nil))
}
