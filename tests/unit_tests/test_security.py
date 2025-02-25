from pathlib import Path

import ldap
from pytest import MonkeyPatch

from mealie.core import security
from mealie.core.config import get_app_settings
from mealie.core.dependencies import validate_file_token
from mealie.db.db_setup import session_context
from tests.utils.factories import random_string


class LdapConnMock:
    def __init__(self, user, password, admin, query_bind, query_password, mail, name) -> None:
        self.app_settings = get_app_settings()
        self.user = user
        self.password = password
        self.query_bind = query_bind
        self.query_password = query_password
        self.admin = admin
        self.mail = mail
        self.name = name

    def simple_bind_s(self, dn, bind_pw):
        if dn == "cn={}, {}".format(self.user, self.app_settings.LDAP_BASE_DN):
            valid_password = self.password
        elif "cn={}, {}".format(self.query_bind, self.app_settings.LDAP_BASE_DN):
            valid_password = self.query_password

        if bind_pw == valid_password:
            return

        raise ldap.INVALID_CREDENTIALS

    # Default search mock implementation
    def search_s(self, dn, scope, filter, attrlist):
        if filter == self.app_settings.LDAP_ADMIN_FILTER:
            assert attrlist == []
            assert filter == self.app_settings.LDAP_ADMIN_FILTER
            assert dn == "cn={}, {}".format(self.user, self.app_settings.LDAP_BASE_DN)
            assert scope == ldap.SCOPE_BASE

            if not self.admin:
                return []

            return [(dn, {})]

        assert attrlist == [
            self.app_settings.LDAP_ID_ATTRIBUTE,
            self.app_settings.LDAP_NAME_ATTRIBUTE,
            self.app_settings.LDAP_MAIL_ATTRIBUTE,
        ]
        assert filter == self.app_settings.LDAP_USER_FILTER.format(
            id_attribute=self.app_settings.LDAP_ID_ATTRIBUTE,
            mail_attribute=self.app_settings.LDAP_MAIL_ATTRIBUTE,
            input=self.user,
        )
        assert dn == self.app_settings.LDAP_BASE_DN
        assert scope == ldap.SCOPE_SUBTREE

        return [
            (
                "cn={}, {}".format(self.user, self.app_settings.LDAP_BASE_DN),
                {
                    self.app_settings.LDAP_ID_ATTRIBUTE: [self.user.encode()],
                    self.app_settings.LDAP_NAME_ATTRIBUTE: [self.name.encode()],
                    self.app_settings.LDAP_MAIL_ATTRIBUTE: [self.mail.encode()],
                },
            )
        ]

    def set_option(self, option, invalue):
        pass

    def unbind_s(self):
        pass


def setup_env(monkeypatch: MonkeyPatch):
    user = random_string(10)
    mail = random_string(10)
    name = random_string(10)
    password = random_string(10)
    query_bind = random_string(10)
    query_password = random_string(10)
    base_dn = "(dc=example,dc=com)"
    monkeypatch.setenv("LDAP_AUTH_ENABLED", "true")
    monkeypatch.setenv("LDAP_SERVER_URL", "")  # Not needed due to mocking
    monkeypatch.setenv("LDAP_BASE_DN", base_dn)
    monkeypatch.setenv("LDAP_QUERY_BIND", query_bind)
    monkeypatch.setenv("LDAP_QUERY_PASSWORD", query_password)
    monkeypatch.setenv("LDAP_USER_FILTER", "(&(objectClass=user)(|({id_attribute}={input})({mail_attribute}={input})))")

    return user, mail, name, password, query_bind, query_password


def test_create_file_token():
    file_path = Path(__file__).parent
    file_token = security.create_file_token(file_path)

    assert file_path == validate_file_token(file_token)


def test_ldap_authentication_mocked(monkeypatch: MonkeyPatch):
    user, mail, name, password, query_bind, query_password = setup_env(monkeypatch)

    def ldap_initialize_mock(url):
        assert url == ""
        return LdapConnMock(user, password, False, query_bind, query_password, mail, name)

    monkeypatch.setattr(ldap, "initialize", ldap_initialize_mock)

    get_app_settings.cache_clear()

    with session_context() as session:
        result = security.authenticate_user(session, user, password)

    assert result
    assert result.username == user
    assert result.email == mail
    assert result.full_name == name
    assert result.admin is False


def test_ldap_authentication_failed_mocked(monkeypatch: MonkeyPatch):
    user, mail, name, password, query_bind, query_password = setup_env(monkeypatch)

    def ldap_initialize_mock(url):
        assert url == ""
        return LdapConnMock(user, password, False, query_bind, query_password, mail, name)

    monkeypatch.setattr(ldap, "initialize", ldap_initialize_mock)

    get_app_settings.cache_clear()

    with session_context() as session:
        result = security.authenticate_user(session, user, password + "a")

    assert result is False


def test_ldap_authentication_non_admin_mocked(monkeypatch: MonkeyPatch):
    user, mail, name, password, query_bind, query_password = setup_env(monkeypatch)
    monkeypatch.setenv("LDAP_ADMIN_FILTER", "(memberOf=cn=admins,dc=example,dc=com)")

    def ldap_initialize_mock(url):
        assert url == ""
        return LdapConnMock(user, password, False, query_bind, query_password, mail, name)

    monkeypatch.setattr(ldap, "initialize", ldap_initialize_mock)

    get_app_settings.cache_clear()

    with session_context() as session:
        result = security.authenticate_user(session, user, password)

    assert result
    assert result.username == user
    assert result.email == mail
    assert result.full_name == name
    assert result.admin is False


def test_ldap_authentication_admin_mocked(monkeypatch: MonkeyPatch):
    user, mail, name, password, query_bind, query_password = setup_env(monkeypatch)
    monkeypatch.setenv("LDAP_ADMIN_FILTER", "(memberOf=cn=admins,dc=example,dc=com)")

    def ldap_initialize_mock(url):
        assert url == ""
        return LdapConnMock(user, password, True, query_bind, query_password, mail, name)

    monkeypatch.setattr(ldap, "initialize", ldap_initialize_mock)

    get_app_settings.cache_clear()

    with session_context() as session:
        result = security.authenticate_user(session, user, password)

    assert result
    assert result.username == user
    assert result.email == mail
    assert result.full_name == name
    assert result.admin


def test_ldap_authentication_disabled_mocked(monkeypatch: MonkeyPatch):
    monkeypatch.setenv("LDAP_AUTH_ENABLED", "False")

    user = random_string(10)
    password = random_string(10)

    class LdapConnMock:
        def simple_bind_s(self, dn, bind_pw):
            assert False  # When LDAP is disabled, this method should not be called

        def search_s(self, dn, scope, filter, attrlist):
            pass

        def set_option(self, option, invalue):
            pass

        def unbind_s(self):
            pass

    def ldap_initialize_mock(url):
        assert url == ""
        return LdapConnMock()

    monkeypatch.setattr(ldap, "initialize", ldap_initialize_mock)

    get_app_settings.cache_clear()

    with session_context() as session:
        security.authenticate_user(session, user, password)
