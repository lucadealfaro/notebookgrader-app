# See https://developers.google.com/identity/protocols/oauth2/web-server#python

import json

import google_auth_oauthlib.flow
import google.oauth2.credentials
from googleapiclient.discovery import build

from py4web import request, redirect, URL, HTTP
from common import session
from pydal import Field

class GoogleScopedLogin(object):
    """Class that enables google login via oauth2 with additional scopes.
    The authorization info is saved so the scopes can be used later on."""

    # These values are used for the plugin registration.
    name = "oauth2googlescoped"
    label = "Google Scoped"
    callback_url = "auth/plugin/oauth2googlescoped/callback"

    def __init__(self, secrets_file, scopes, db=None, define_tables=True):
        """
        Creates an authorization object for Google with Oauth2 and paramters.
        Args:
            secrets_file: file with secrets for Oauth2.
            scopes: scopes desired.
                See https://developers.google.com/drive/api/guides/api-specific-auth
                and https://developers.google.com/identity/protocols/oauth2/scopes
            db:
            define_tables:
        """

        # Local secrets to be able to access.
        self.secrets_file = secrets_file
        # Scopes for which we ask authorization
        self.scopes = ["openid",
                       "https://www.googleapis.com/auth/userinfo.email",
                       "https://www.googleapis.com/auth/userinfo.profile"] + scopes
        self.db = db
        if db and define_tables:
            self._define_tables()


    def _define_tables(self):
        self.db.define_table('auth_credentials', [
            Field('email'),
            Field('credentials') # Stored in Json for generality.
        ])


    def get_login_url(self, state=None, next=None):
        # Creates a flow.
        flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
            self.secrets_file, scopes=self.scopes)
        # Sets its callback URL.  This is the local URL that will be called
        # once the user gives permission.
        vars = {}
        if next:
            vars["next"] = next
        """Returns the URL to which the user is directed."""
        flow.redirect_uri = URL(self.callback_url, vars=vars, scheme=True)
        authorization_url, state = flow.authorization_url(
            # Enable offline access so that you can refresh an access token without
            # re-prompting the user for permission. Recommended for web server apps.
            access_type='offline',
            # Enable incremental authorization. Recommended as a best practice.
            include_granted_scopes='true')
        session["oauth2googlescoped:state"] = state
        return authorization_url


    def handle_request(self, auth, path, get_vars, post_vars):
        """Handles the login request or the callback."""
        if path == "login":
            auth.session["_next"] = request.query.get("next") or URL("index")
            redirect(self.get_login_url())
        elif path == "callback":
            self._handle_callback(auth, get_vars)
        else:
            raise HTTP(404)

    def _handle_callback(self, auth, get_vars):
        # Builds a flow again, this time with the state in it.
        state = session["oauth2googlescoped:state"]
        flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
            self.secrets_file, scopes=self.scopes, state=state)
        flow.redirect_uri = URL(self.callback_url, vars=vars, scheme=True)
        # Use the authorization server's response to fetch the OAuth 2.0 tokens.
        if state and get_vars.get('state', None) != state:
            raise HTTP(401, "Invalid state")
        error = get_vars.get("error")
        if error:
            if isinstance(error, str):
                code, msg = 401, error
            else:
                code = error.get("code", 401)
                msg = error.get("message", "Unknown error")
            raise HTTP(code, msg)
        if not 'code' in get_vars:
            raise HTTP(401, "Missing code parameter in response.")
        code = get_vars.get('code')
        flow.fetch_token(code=code)
        # We got the credentials!
        credentials = flow.credentials
        # Now we must use the credentials to check the user identity.
        # see https://github.com/googleapis/google-api-python-client/pull/1088/files
        # and https://github.com/googleapis/google-api-python-client/issues/1071
        # and ??
        user_info_service = build('oauth2', 'v2', credentials=credentials)
        user_info = user_info_service.userinfo().get().execute()
        email = user_info.get("email")
        print("User_info:", user_info)
        print("Email:", email)
        if email is None:
            raise HTTP(401, "Missing email")
        # Finally, we store the credentials, so we can re-use them in order
        # to use the scopes we requested.
        credentials_json=json.dumps(self.credentials_to_dict(credentials))
        self.db.auth_credentials.update_or_insert(
            self.db.auth_credentials.email == email,
            email=email,
            credentials=credentials_json
        )
        self.db.commit()
        # Logs in the user.
        auth.store_user_in_session(email)
        if "_next" in auth.session:
            next = auth.session.get("_next")
            del auth.session["_next"]
        else:
            next = URL("index")
        redirect(next)


    @staticmethod
    def credentials_to_dict(credentials):
        return {'token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'token_uri': credentials.token_uri,
                'client_id': credentials.client_id,
                'client_secret': credentials.client_secret,
                'scopes': credentials.scopes}

    @staticmethod
    def credentials_from_dict(credentials_dict):
        return google.oauth2.credentials.Credentials(**credentials_dict)

    def etc(self):
        google_auth_oauthlib.flow.Flow.from_client_config()