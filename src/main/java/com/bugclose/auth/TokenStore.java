package com.bugclose.auth;

import org.springframework.stereotype.Component;

import java.security.SecureRandom;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 内存 token 存储：登录签发、请求校验、登出注销。单实例足够；重启后所有用户需重新登录。
 */
@Component
public class TokenStore {

    private static final long TTL_MS = 12 * 60 * 60 * 1000L; // 12 小时

    private final Map<String, Entry> store = new ConcurrentHashMap<>();
    private final SecureRandom random = new SecureRandom();

    private record Entry(long userId, long expireAt) {
        boolean expired() {
            return System.currentTimeMillis() > expireAt;
        }
    }

    /** 签发 token */
    public String issue(long userId) {
        byte[] buf = new byte[32];
        random.nextBytes(buf);
        StringBuilder sb = new StringBuilder(64);
        for (byte b : buf) {
            sb.append(String.format("%02x", b));
        }
        String token = sb.toString();
        store.put(token, new Entry(userId, System.currentTimeMillis() + TTL_MS));
        return token;
    }

    /** 校验 token，未过期返回 userId，否则 null */
    public Long resolve(String token) {
        if (token == null || token.isBlank()) {
            return null;
        }
        Entry e = store.get(token);
        if (e == null) {
            return null;
        }
        if (e.expired()) {
            store.remove(token);
            return null;
        }
        return e.userId;
    }

    public void revoke(String token) {
        if (token != null) {
            store.remove(token);
        }
    }
}
