package com.bugclose.auth;

import org.springframework.stereotype.Component;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 登录限流（内存级）：同一 用户名+IP 在窗口期内连续失败超过阈值后锁定一段时间，防爆破。
 * 单实例够用，重启后计数清零。
 */
@Component
public class LoginRateLimiter {

    /** 窗口期 10 分钟 */
    private static final long WINDOW_MS = 10 * 60 * 1000L;
    /** 窗口期内允许的最大失败次数 */
    private static final int MAX_FAILURES = 5;
    /** 触发锁定后的锁定时长 10 分钟 */
    private static final long LOCK_MS = 10 * 60 * 1000L;

    private record Entry(int failures, long windowStart, long lockedUntil) {
    }

    private final Map<String, Entry> attempts = new ConcurrentHashMap<>();

    /** 登录前检查：处于锁定状态则抛 LoginRateLimitException */
    public void checkAllowed(String username, String ip) {
        Entry e = attempts.get(key(username, ip));
        if (e == null) {
            return;
        }
        long now = System.currentTimeMillis();
        if (now < e.lockedUntil()) {
            long remainSec = (e.lockedUntil() - now) / 1000;
            throw new LoginRateLimitException(
                    "失败次数过多，账号已临时锁定，请 " + Math.max(1, remainSec / 60) + " 分钟后再试");
        }
    }

    /** 登录成功后调用：清除失败记录 */
    public void onSuccess(String username, String ip) {
        attempts.remove(key(username, ip));
    }

    /** 登录失败后调用：累计失败次数，超过阈值则锁定 */
    public void onFailure(String username, String ip) {
        long now = System.currentTimeMillis();
        attempts.compute(key(username, ip), (k, old) -> {
            if (old == null || now - old.windowStart() > WINDOW_MS) {
                return new Entry(1, now, 0);
            }
            int failures = old.failures() + 1;
            long lockedUntil = failures >= MAX_FAILURES ? now + LOCK_MS : 0;
            return new Entry(failures, old.windowStart(), lockedUntil);
        });
    }

    private String key(String username, String ip) {
        return (username == null ? "" : username.toLowerCase()) + '|' + (ip == null ? "" : ip);
    }

    /** 登录限流异常，由 GlobalExceptionHandler 映射为 429 */
    public static class LoginRateLimitException extends RuntimeException {
        public LoginRateLimitException(String message) {
            super(message);
        }
    }
}
