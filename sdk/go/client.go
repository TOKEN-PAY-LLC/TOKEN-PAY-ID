// Package tpid provides the official Go SDK for TOKEN PAY ID.
// https://tokenpay.space/docs
package tpid

import (
	"bytes"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"
)

const defaultBaseURL = "https://tokenpay.space"

// Config holds the client configuration.
type Config struct {
	ClientID     string
	ClientSecret string
	RedirectURI  string
	BaseURL      string // optional, defaults to https://tokenpay.space
}

// Client is the TOKEN PAY ID API client.
type Client struct {
	cfg        Config
	httpClient *http.Client
}

// NewClient creates a new TOKEN PAY ID client.
func NewClient(cfg Config) *Client {
	if cfg.BaseURL == "" {
		cfg.BaseURL = defaultBaseURL
	}
	cfg.BaseURL = strings.TrimRight(cfg.BaseURL, "/")
	return &Client{
		cfg:        cfg,
		httpClient: &http.Client{Timeout: 15 * time.Second},
	}
}

// User represents a TOKEN PAY ID user.
type User struct {
	ID               string `json:"id"`
	Email            string `json:"email"`
	Name             string `json:"name"`
	Role             string `json:"role"`
	EmailVerified    bool   `json:"email_verified"`
	TwoFactorEnabled bool   `json:"two_factor_enabled"`
	Locale           string `json:"locale"`
	CreatedAt        string `json:"created_at"`
	LastLogin        string `json:"last_login"`
}

// TokenResponse is returned from the token endpoint.
type TokenResponse struct {
	AccessToken  string `json:"access_token"`
	RefreshToken string `json:"refresh_token"`
	TokenType    string `json:"token_type"`
	ExpiresIn    int    `json:"expires_in"`
	User         *User  `json:"user,omitempty"`
}

// PKCEPair holds a PKCE verifier and S256 challenge.
type PKCEPair struct {
	Verifier  string
	Challenge string
}

// Error represents a TOKEN PAY ID API error.
type Error struct {
	Code    string `json:"code"`
	Message string `json:"message"`
	Status  int    `json:"status"`
}

func (e *Error) Error() string {
	return fmt.Sprintf("TOKEN PAY ID error %d [%s]: %s", e.Status, e.Code, e.Message)
}

// GeneratePKCE creates a PKCE verifier + S256 challenge pair.
func GeneratePKCE() (*PKCEPair, error) {
	b := make([]byte, 32)
	if _, err := rand.Read(b); err != nil {
		return nil, err
	}
	verifier := base64.RawURLEncoding.EncodeToString(b)
	sum := sha256.Sum256([]byte(verifier))
	challenge := base64.RawURLEncoding.EncodeToString(sum[:])
	return &PKCEPair{Verifier: verifier, Challenge: challenge}, nil
}

// GetAuthorizationURL builds the OAuth 2.0 authorization URL.
func (c *Client) GetAuthorizationURL(scope, state, codeChallenge string) string {
	if scope == "" {
		scope = "profile email"
	}
	params := url.Values{
		"client_id":     {c.cfg.ClientID},
		"redirect_uri":  {c.cfg.RedirectURI},
		"response_type": {"code"},
		"scope":         {scope},
	}
	if state != "" {
		params.Set("state", state)
	}
	if codeChallenge != "" {
		params.Set("code_challenge", codeChallenge)
		params.Set("code_challenge_method", "S256")
	}
	return c.cfg.BaseURL + "/api/v1/oauth/authorize?" + params.Encode()
}

// ExchangeCode exchanges an authorization code for tokens.
func (c *Client) ExchangeCode(code, codeVerifier string) (*TokenResponse, error) {
	body := map[string]string{
		"grant_type":    "authorization_code",
		"code":          code,
		"client_id":     c.cfg.ClientID,
		"client_secret": c.cfg.ClientSecret,
		"redirect_uri":  c.cfg.RedirectURI,
	}
	if codeVerifier != "" {
		body["code_verifier"] = codeVerifier
	}
	var resp TokenResponse
	if err := c.post("/api/v1/oauth/token", body, &resp); err != nil {
		return nil, err
	}
	return &resp, nil
}

// RefreshToken refreshes an access token.
func (c *Client) RefreshToken(refreshToken string) (*TokenResponse, error) {
	body := map[string]string{
		"grant_type":    "refresh_token",
		"refresh_token": refreshToken,
		"client_id":     c.cfg.ClientID,
		"client_secret": c.cfg.ClientSecret,
	}
	var resp TokenResponse
	if err := c.post("/api/v1/oauth/token", body, &resp); err != nil {
		return nil, err
	}
	return &resp, nil
}

// GetUser retrieves the authenticated user via the OIDC userinfo endpoint.
func (c *Client) GetUser(accessToken string) (*User, error) {
	var user User
	if err := c.get("/api/v1/oauth/userinfo", accessToken, &user); err != nil {
		return nil, err
	}
	return &user, nil
}

// GetMe retrieves the full authenticated user profile.
func (c *Client) GetMe(accessToken string) (*User, error) {
	var result struct {
		User User `json:"user"`
	}
	if err := c.get("/api/v1/users/me", accessToken, &result); err != nil {
		// try direct unmarshal
		var user User
		if err2 := c.get("/api/v1/users/me", accessToken, &user); err2 != nil {
			return nil, err
		}
		return &user, nil
	}
	if result.User.ID != "" {
		return &result.User, nil
	}
	return nil, fmt.Errorf("unexpected response")
}

// RevokeToken revokes an access or refresh token.
func (c *Client) RevokeToken(token string) error {
	body := map[string]string{
		"token":         token,
		"client_id":     c.cfg.ClientID,
		"client_secret": c.cfg.ClientSecret,
	}
	var resp map[string]interface{}
	return c.post("/api/v1/oauth/revoke", body, &resp)
}

// ── INTERNAL ──────────────────────────────────────────────────────────────────

func (c *Client) post(path string, body interface{}, out interface{}) error {
	b, _ := json.Marshal(body)
	req, err := http.NewRequest("POST", c.cfg.BaseURL+path, bytes.NewReader(b))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	return c.do(req, out)
}

func (c *Client) get(path, token string, out interface{}) error {
	req, err := http.NewRequest("GET", c.cfg.BaseURL+path, nil)
	if err != nil {
		return err
	}
	req.Header.Set("Authorization", "Bearer "+token)
	return c.do(req, out)
}

func (c *Client) do(req *http.Request, out interface{}) error {
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	data, _ := io.ReadAll(resp.Body)
	if resp.StatusCode >= 400 {
		var errResp struct {
			Error Error `json:"error"`
		}
		json.Unmarshal(data, &errResp)
		if errResp.Error.Code != "" {
			return &errResp.Error
		}
		return fmt.Errorf("HTTP %d: %s", resp.StatusCode, string(data))
	}
	return json.Unmarshal(data, out)
}
