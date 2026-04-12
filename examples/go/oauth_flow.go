// TOKEN PAY ID — Go OAuth 2.0 + PKCE Example
// Run: go run oauth_flow.go
package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"sync"

	tpid "github.com/TOKEN-PAY-LLC/TOKEN-PAY-ID/sdk/go"
)

var (
	client     *tpid.Client
	stateStore sync.Map // map[state]pkceVerifier
)

func main() {
	client = tpid.NewClient(tpid.Config{
		ClientID:     os.Getenv("TPID_PUBLIC_KEY"),
		ClientSecret: os.Getenv("TPID_SECRET_KEY"),
		RedirectURI:  "http://localhost:8080/callback",
	})

	http.HandleFunc("/login", handleLogin)
	http.HandleFunc("/callback", handleCallback)
	http.HandleFunc("/me", handleMe)

	fmt.Println("TOKEN PAY ID example running at http://localhost:8080")
	fmt.Println("Open http://localhost:8080/login to start")
	log.Fatal(http.ListenAndServe(":8080", nil))
}

// 1. Start login
func handleLogin(w http.ResponseWriter, r *http.Request) {
	pkce, err := tpid.GeneratePKCE()
	if err != nil {
		http.Error(w, "PKCE error: "+err.Error(), 500)
		return
	}

	state := randomString(16)
	stateStore.Store(state, pkce.Verifier)

	url := client.GetAuthorizationURL("openid profile email", state, pkce.Challenge)
	http.Redirect(w, r, url, http.StatusFound)
}

// 2. Handle OAuth callback
func handleCallback(w http.ResponseWriter, r *http.Request) {
	errParam := r.URL.Query().Get("error")
	if errParam != "" {
		http.Error(w, "Auth error: "+errParam, 400)
		return
	}

	code := r.URL.Query().Get("code")
	state := r.URL.Query().Get("state")
	if code == "" || state == "" {
		http.Error(w, "Missing code or state", 400)
		return
	}

	verifierVal, ok := stateStore.LoadAndDelete(state)
	if !ok {
		http.Error(w, "Invalid state — possible CSRF", 400)
		return
	}
	verifier := verifierVal.(string)

	tokens, err := client.ExchangeCode(code, verifier)
	if err != nil {
		http.Error(w, "Token exchange failed: "+err.Error(), 401)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"message":       "Login successful",
		"user":          tokens.User,
		"access_token":  tokens.AccessToken,
		"refresh_token": tokens.RefreshToken,
		"expires_in":    tokens.ExpiresIn,
	})
}

// 3. Protected route example
func handleMe(w http.ResponseWriter, r *http.Request) {
	token := r.Header.Get("Authorization")
	if len(token) > 7 && token[:7] == "Bearer " {
		token = token[7:]
	}
	if token == "" {
		http.Error(w, `{"error":"No token"}`, 401)
		return
	}

	user, err := client.GetUser(token)
	if err != nil {
		http.Error(w, `{"error":"`+err.Error()+`"}`, 401)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{"user": user})
}

func randomString(n int) string {
	b := make([]byte, n)
	for i := range b {
		b[i] = "abcdefghijklmnopqrstuvwxyz0123456789"[b[i]%36]
	}
	return string(b)
}
