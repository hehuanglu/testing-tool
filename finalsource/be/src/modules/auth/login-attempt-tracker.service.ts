import { Injectable } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';

interface AttemptState {
  count: number;
  windowStartedAt: number;
  blockedUntil: number;
}

@Injectable()
export class LoginAttemptTracker {
  private readonly states = new Map<string, AttemptState>();
  private readonly maxEntries = 10_000;

  constructor(private readonly config: ConfigService) {}

  isBlocked(key: string, now = Date.now()): boolean {
    const state = this.states.get(key);
    if (!state) return false;
    if (state.blockedUntil > now) return true;
    if (now - state.windowStartedAt >= this.windowMilliseconds) this.states.delete(key);
    return false;
  }

  recordFailure(key: string, now = Date.now()): void {
    const previous = this.states.get(key);
    const state = !previous || now - previous.windowStartedAt >= this.windowMilliseconds
      ? { count: 0, windowStartedAt: now, blockedUntil: 0 }
      : previous;
    state.count += 1;
    if (state.count >= this.config.getOrThrow<number>('app.authentication.maxAttempts')) {
      state.blockedUntil = now + this.config.getOrThrow<number>('app.authentication.lockoutSeconds') * 1000;
    }
    if (!this.states.has(key) && this.states.size >= this.maxEntries) {
      const oldest = this.states.keys().next().value;
      if (typeof oldest === 'string') this.states.delete(oldest);
    }
    this.states.set(key, state);
  }

  reset(key: string): void {
    this.states.delete(key);
  }

  private get windowMilliseconds(): number {
    return this.config.getOrThrow<number>('app.authentication.attemptWindowSeconds') * 1000;
  }
}
