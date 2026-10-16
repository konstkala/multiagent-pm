from app.core.security import new_token
from app.services.email import reset_password_email, to_mime, verification_email


def test_links_survive_encoding_on_one_unbroken_line() -> None:
    token = new_token()
    messages = [verification_email("a@example.com", token), reset_password_email("a@b.c", token)]

    for message in messages:
        raw = to_mime(message, "PM <no-reply@pm.local>").as_string()

        assert "Content-Transfer-Encoding: 7bit" in raw
        # No '=3D' and no soft line break inside the token. SMTP lines end with \r\n.
        assert f"token={token}\r\n" in raw
