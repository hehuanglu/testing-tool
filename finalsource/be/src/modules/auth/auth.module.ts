import { Module } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { JwtModule } from '@nestjs/jwt';
import { TypeOrmModule } from '@nestjs/typeorm';
import { AuthController } from './auth.controller';
import { AuthService } from './auth.service';
import { User } from './entities/user.entity';
import { LoginAttemptTracker } from './login-attempt-tracker.service';
import { JwtStrategy } from './jwt.strategy';
import { JwtAuthGuard } from './jwt-auth.guard';

@Module({
  imports: [
    TypeOrmModule.forFeature([User]),
    JwtModule.registerAsync({
      inject: [ConfigService],
      useFactory: (config: ConfigService) => ({
        secret: config.getOrThrow<string>('app.jwt.secret'),
        signOptions: {
          algorithm: 'HS256',
          expiresIn: config.getOrThrow<number>('app.jwt.expiresInSeconds'),
          issuer: config.getOrThrow<string>('app.jwt.issuer'),
          audience: config.getOrThrow<string>('app.jwt.audience'),
        },
      }),
    }),
  ],
  controllers: [AuthController],
  providers: [AuthService, LoginAttemptTracker, JwtStrategy, JwtAuthGuard],
  exports: [JwtAuthGuard],
})
export class AuthModule {}
