package org.ossustain.security;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.stereotype.Service;

@Service
public class AppUserDetailsService implements UserDetailsService {
    private final JdbcTemplate jdbc;

    public AppUserDetailsService(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @Override
    public AppUserPrincipal loadUserByUsername(String username) throws UsernameNotFoundException {
        var users = jdbc.query("""
                SELECT id, username, password_hash, enabled, must_change_password
                FROM app_users WHERE username = ?
                """, (rs, row) -> new AppUserPrincipal(
                rs.getLong("id"), rs.getString("username"), rs.getString("password_hash"),
                rs.getBoolean("enabled"), rs.getBoolean("must_change_password"), java.util.List.of()),
                username.toLowerCase(java.util.Locale.ROOT));
        if (users.isEmpty()) {
            throw new UsernameNotFoundException("Account not found");
        }
        AppUserPrincipal user = users.getFirst();
        var roles = jdbc.query("SELECT role FROM app_user_roles WHERE user_id = ? ORDER BY role",
                (rs, row) -> rs.getString("role"), user.id());
        return new AppUserPrincipal(user.id(), user.username(), user.password(), user.enabled(),
                user.mustChangePassword(), roles);
    }
}
