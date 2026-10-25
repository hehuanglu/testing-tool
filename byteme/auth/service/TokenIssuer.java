package org.example.auth.service;

import org.example.auth.dto.AccessToken;
import org.example.shared.api.AuthenticatedUser;

public interface TokenIssuer {
    AccessToken issue(AuthenticatedUser user);
}
