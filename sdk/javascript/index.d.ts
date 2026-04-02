export interface TokenPayIDConfig {
    clientId: string;
    clientSecret: string;
    redirectUri: string;
    baseUrl?: string;
}

export interface PKCEPair {
    verifier: string;
    challenge: string;
}

export interface AuthUrlOptions {
    scope?: string;
    state?: string;
    codeChallenge?: string;
}

export interface TokenResponse {
    access_token: string;
    refresh_token: string;
    token_type: string;
    expires_in: number;
    user: User;
}

export interface User {
    id: string;
    email: string;
    name: string;
    role: 'user' | 'enterprise' | 'admin';
    email_verified: boolean;
    two_factor_enabled: boolean;
    locale: string;
    theme: string;
    created_at: string;
    last_login: string;
}

export class TokenPayIDError extends Error {
    code: string;
    status: number;
}

export interface Notification {
    id: string;
    type: string;
    title: string;
    body: string;
    is_read: boolean;
    created_at: string;
}

export interface NotificationsResponse {
    notifications: Notification[];
    unread: number;
}

export class TokenPayIDClient {
    constructor(config: TokenPayIDConfig);
    generatePKCE(): Promise<PKCEPair>;
    getAuthorizationUrl(opts?: AuthUrlOptions): string;
    exchangeCode(code: string, codeVerifier?: string): Promise<TokenResponse>;
    refreshToken(refreshToken: string): Promise<TokenResponse>;
    getUser(accessToken: string): Promise<User>;
    getMe(accessToken: string): Promise<User>;
    revokeToken(token: string): Promise<{ success: boolean }>;
    getNotifications(accessToken: string): Promise<NotificationsResponse>;
    markNotificationRead(accessToken: string, notificationId: string): Promise<{ success: boolean }>;
    markAllNotificationsRead(accessToken: string): Promise<{ success: boolean }>;
    static verifyWebhookSignature(payload: string, signature: string, secret: string, tolerance?: number): boolean;
}
