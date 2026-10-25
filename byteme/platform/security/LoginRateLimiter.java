package org.example.platform.security;
import java.time.Clock;
import java.util.HashMap;
import java.util.Map;
public final class LoginRateLimiter {
    public static final class LimitExceeded extends RuntimeException {
        private final long retry; public LimitExceeded(long retry) { super("LOGIN_RATE_LIMITED");this.retry=retry; }
        public long retryAfter() { return retry; }
    }
    private record Bucket(long start,int count) {}
    private final Map<String,Bucket> buckets=new HashMap<>();
    private final Clock clock;private final int emailLimit,ipLimit;private final long window;
    private long nextCleanup;
    public LoginRateLimiter(Clock clock,int emailLimit,int ipLimit,long window) {
        if(emailLimit<=0 || ipLimit<=0 || window<=0) throw new IllegalArgumentException("Quota phải dương");
        this.clock=clock;this.emailLimit=emailLimit;this.ipLimit=ipLimit;this.window=window;
    }
    public void email(String email) { take("email:"+email,emailLimit); }
    public void ip(String ip) { take("ip:"+ip,ipLimit); }
    private synchronized void take(String key,int limit) {
        long now=clock.instant().getEpochSecond();
        if(now>=nextCleanup) { buckets.entrySet().removeIf(e->now>=e.getValue().start()+window);nextCleanup=now+window; }
        Bucket old=buckets.get(key);
        if(old!=null && now>=old.start()+window) old=null;
        if(old!=null && old.count()>=limit) throw new LimitExceeded(Math.max(1,old.start()+window-now));
        if(old==null && buckets.size()>=100000) throw new LimitExceeded(window);
        buckets.put(key,old==null?new Bucket(now,1):new Bucket(old.start(),old.count()+1));
    }
}
