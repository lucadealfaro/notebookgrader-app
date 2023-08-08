import collections
import datetime
from py4web import action, URL, request, HTTP
from yatl.helpers import XML
from py4web.utils.url_signer import URLSigner
from py4web.core import Fixture
from pydal.validators import *

class VueForm(Fixture):
    """This is a prototype class for building client-side forms with
    validation."""

    FORM = '<vueform url="{url}" check_url="{check_url}" cancel_url="{cancel_url}"></vueform>'

    TYPE_CONVERSION = {
        "boolean": "checkbox",
        "date": "date",
        "datetime": "datetime",
        "password": "password",
        "text": "textarea",
        "integer": "number",
        "double": "number",
        "string": "text",
    }

    def __init__(
        self,
        fields_or_table,
        session,
        path,
        readonly=False,
        signer=None,
        db=None,
        auth=None,
        use_id=False,
        validate=None,
    ):
        """fields_or_table is a list of Fields from DAL, or a table.
        If a table is passed, the fields that are marked writable
        (or readable, if readonly=True) are included.
        session is used to sign the URLs.
        The other parameters are optional, and are used only
        if they will be needed to process the get and post metods.
        @param fields_or_table: list of Field for a database table, or table itself.
        @param session: session, used to validate access and sign.
        @param path: path used for form GET/POST
        @param readonly: If true, the form is readonly.
        @param signer: signer for URLs, or else, a new signer is created.
        @param db: database.  Used by implementation.
        @param auth: auth.  Used by implementation.
        @param use_id: use an ID in the AJAX callbacks.
        @param validate: A function that takes as arguments the dictionary of
            fields, and performs any desired extra validation.  If an error is
            set, then the form is not acted upon, and the error is shown to the user.
        """
        assert session is not None, "You must provide a session."
        self.path_form = path + "/form"
        self.path_check = path + "/check"
        self.db = db
        self.signer = signer or URLSigner(session)
        self.__prerequisites__ = [session, self.signer]
        self.validate = validate
        # Creates entry points for giving the blank form, and processing form submissions.
        # There are three entry points:
        # - Form setup GET: This gets how the form is set up, including the types of the fields.
        # - Form GET: This gets the values of the fields.
        # - Form PUT: This gives the values of the fields, and performs whatever
        #   action needs to be peformed.
        # This division is done so that the GET and PUT action, but not the setup_GET,
        # need to be over-ridden when the class is subclassed.
        url_params = ["<id>"] if use_id else []
        self.use_id = use_id
        # NOTE: we need a list below, as the iterator otherwise can be used only once.
        # Iterators by default are a very lame idea indeed.
        args = list(filter(None, [session, db, auth, self.signer.verify()]))
        f = action.uses(*args)(self.get)
        # print("Registering:", "/".join([self.path_form] + url_params))
        action("/".join([self.path_form] + url_params), method=["GET"])(f)
        f = action.uses(*args)(self.post)
        action("/".join([self.path_form] + url_params), method=["POST"])(f)
        f = action.uses(*args)(self.validate_field)
        action("/".join([self.path_check] + url_params), method=["POST"])(f)
        # Stores the parameters that are necessary for creating the form.
        # Generates the list of field descriptions.
        self.readonly = readonly
        self.fields = collections.OrderedDict()
        for field in fields_or_table:
            self.fields[field.name] = field


    def _get_fields_for_web(self, values):
        """Returns a dictionary mapping each field to information that is ready
        to be sent to the web app.
        """
        fields = collections.OrderedDict()
        for f_name, f in self.fields.items():
            # We only include readable fields.
            if f.readable:
                # Formats the field.
                v = values.get(f_name)
                if v is None and hasattr(f, "default"):
                    v = f.default() if callable(f.default) else f.default
                # Builds a default web field.
                web_field = dict(
                    name=f_name,
                    writable=f.writable and not self.readonly,
                    label=f.label,
                    help=f.help if hasattr(f, 'help') else None,
                    type=VueForm.TYPE_CONVERSION.get(f.type, "text"),
                    placeholder=f.placeholder if hasattr(f, "placeholder") else None,
                    comment=f.comment if hasattr(f, "comment") else None,
                    value=v,
                )
                # Adapts the web field to specific types of fields.
                # Datetime
                if f.type == "datetime":
                    # Converts the field to the format expected by the web interface.
                    web_field["value"] = v + "Z" if v else None
                # Dropdown
                if isinstance(f.requires, IS_IN_SET):
                    if not f.writable:
                        if isinstance(v, list):
                            web_field["value"] = ", ".join(v)
                        else:
                            web_field["value"] = v
                    else:
                        theset = f.requires.theset
                        labels = f.requires.labels or theset
                        if f.requires.zero:
                            theset.insert(0, "")
                        vals = [dict(text=l, label=k) for (l, k) in zip(labels, theset)]
                        web_field["type"] = "dropdown"
                        web_field["values"] = vals
                        web_field["multiple"] = f.requires.multiple
                fields[f.name] = web_field
        return fields

    def read_values(self, record_id):
        """
        Can be overridden.
        The function must return the data to fill the form.
        This must return a dictionary mapping each field name to a field value.
        This function should be over-ridden.
        @param record_id: can be either None, e.g. for an insertion form, or the id of
            something that has to be read to be edited / viewed.
        """
        values = {}
        for f_name, f in self.fields.items():
            values[f_name] = f.formatter(None)
        return values

    def get(self, id=None):
        """Returns the info necessary to display the form: a list of fields,
        filled with values."""
        # Gets the values from the fields.
        record_id = None if id == "None" else id
        values = self.read_values(record_id)
        web_fields = self._get_fields_for_web(values)
        response = []
        for n, f in web_fields.items():
            response.append(f)
        return dict(fields=list(web_fields.values()), readonly=self.readonly)

    def __call__(self, id=None, cancel_url=''):
        """This method returns the element that can be included in the page.
        The *args and **kwargs are used when subclassing, to allow for forms
        that are 'custom built' for some need.
        """
        return XML(VueForm.FORM.format(
            url=self.url(id),
            check_url=self.check_url(id),
            cancel_url=cancel_url,
        ))

    def url(self, id):
        return URL(*filter(None, [self.path_form, id]), signer=self.signer)

    def check_url(self, id):
        return URL(*filter(None, [self.path_check, id]), signer=self.signer)

    def validate_field(self, id=None):
        """Validates one field, called from the client."""
        name = request.json["name"]
        record_id = None if id == "None" else id
        # Gets the default for that field, if specified.
        f = self.fields[name]
        value = request.json.get("value", f.default)
        error = None
        if hasattr(f, "validate"):
            _, error = f.validate(value, record_id=record_id)
        return dict(error=error)

    def _validate_one_field(self, f_name, f_value, record_id=None):
        """Validates one field, returning the error if any, else None.
        The record_id is used by the validators."""
        f = self.fields[f_name]
        if hasattr(f, "validate"):
            validated_value, error = f.validate(f_value, record_id)
        else:
            validated_value, error = f_value, None
        return validated_value, error

    def validate_form(self, record_id=None):
        """Validates an entire form. Returns two dictionaries:
        one mapping names to validated field values (for use by the app),
        and one mapping names to errors, to return to the web browser.
        If the latter dict is empty then there are no errors."""
        validated_dict = {}
        error_dict = {}
        # First performs the valuation on each field.
        for f_name, f in self.fields.items():
            f_value = request.json.get(f_name)
            v, e = self._validate_one_field(f_name, f_value, record_id=record_id)
            validated_dict[f_name] = v
            if e is not None:
                error_dict[f_name] = e
        # If an additional validation function is specified, uses it.
        if self.validate is not None and len(error_dict) == 0:
            error_dict.update(self.validate(self.fields, validated_dict))
        return validated_dict, error_dict

    def post(self, id=None):
        """Processes the form submission. The return value is the same as for get.
        """
        record_id = None if id == "None" else id
        validated_dict, error_dict = self.validate_form(record_id=record_id)
        if len(error_dict) > 0:
            # Reports the errors to the web app.
            return dict(errors=error_dict)
        else:
            # We do not want to overwrite the record id.
            if "id" in validated_dict:
                del validated_dict["id"]
            return self.process_post(record_id, validated_dict)

    def process_post(self, id, validated_values):
        """This function should be over-ridden.  It processes the post.
        @param id: id of the item; can be None for a create;
        @param validated_values: dictionary from field name to field value."""
        return None
