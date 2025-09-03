

// src/app/static/js/api.js
// Centralized API utilities with normalized error handling.
// Works with our server's error schema: { error: { type, code, message, request_id, details } }
// Backward-compatible: returns an object with { ok, status, json, message } instead of throwing.

(function (global) {
    "use strict";

    function toast(msg) {
        // Minimal toast; replace with a nicer UI later.
        alert(msg);
    }

    function normalizeError(payload) {
        // Accept raw payload or already-unwrapped error and normalize.
        if (!payload) return { type: "UnknownError", code: "unknown", message: "Unknown error" };
        if (payload.error && typeof payload.error === "object") return payload.error;
        if (payload.type || payload.code || payload.message) return payload;
        return { type: "UnknownError", code: "unknown", message: String(payload) };
    }

    function humanizeApiError(payloadOrError) {
        const err = normalizeError(payloadOrError);
        const msg = err && typeof err.message === "string" ? err.message : null;
        switch (err.code) {
            case "duplicate":
                return msg || "That name already exists. Try another.";
            case "not_found":
                return msg || "We couldn’t find that item.";
            case "permission_denied":
                return msg || "You don’t have permission to do that.";
            case "validation_error":
                return msg || "Please check your input and try again.";
            case "bad_request":
                return msg || "Your request is invalid.";
            case "conflict":
                return msg || "This action conflicts with the current state.";
            case "rate_limited":
                return msg || "Too many requests. Please try again shortly.";
            case "external_service_error":
                return msg || "Upstream service error. Please try again.";
            case "database_error":
                return msg || "Temporary database issue. Please retry.";
            case "internal_error":
                return msg || "Something went wrong on our side.";
            default:
                return msg || "Unexpected error. Please try again.";
        }
    }

    async function request(method, path, body) {
        const res = await fetch(path, {
            method,
            headers: { "Content-Type": "application/json" },
            body: body != null ? JSON.stringify(body) : undefined,
        });
        let json = null;
        try { json = await res.json(); } catch (_) { }
        return { res, json };
    }

    async function api(method, path, body) {
        const { res, json } = await request(method, path, body);
        if (!res.ok) {
            const err = normalizeError(json || { message: res.statusText, code: "unknown" });
            const message = humanizeApiError(err);
            return { ok: false, status: res.status, json, error: err, message };
        }
        return { ok: true, status: res.status, json };
    }

    // UMD-lite export: attach to window and also support ESM/CommonJS if present
    const Api = { api, request, toast, humanizeApiError };
    if (typeof module !== "undefined" && module.exports) module.exports = Api;
    if (typeof window !== "undefined") global.AppApi = Api;
})(typeof window !== "undefined" ? window : this);