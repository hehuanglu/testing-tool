import { Injectable, UnauthorizedException } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { PassportStrategy } from '@nestjs/passport';
import { ExtractJwt, Strategy } from 'passport-jwt';

interface JwtPayload {
  sub?: unknown;
}

export interface AuthenticatedPrincipal {
  userId: number;
}

@Injectable()
export class JwtStrategy extends PassportStrategy(Strategy) {
  constructor(config: ConfigService) {
    super({
      jwtFromRequest: ExtractJwt.fromAuthHeaderAsBearerToken(),
      ignoreExpiration: false,
      secretOrKey: config.getOrThrow<string>('app.jwt.secret'),
      issuer: config.getOrThrow<string>('app.jwt.issuer'),
      audience: config.getOrThrow<string>('app.jwt.audience'),
      algorithms: ['HS256'],
    });
  }

  validate(payload: JwtPayload): AuthenticatedPrincipal {
    if (!Number.isInteger(payload.sub) || (payload.sub as number) < 1) {
      throw new UnauthorizedException('Invalid access token.');
    }
    return { userId: payload.sub as number };
  }
}
