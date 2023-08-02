// This will be the object that will contain the Vue attributes
// and be used to initialize it.
let app = {};


// Given an empty app object, initializes it filling its attributes,
// creates a Vue instance, and then initializes the Vue instance.
let init = (app) => {

    // This is the Vue data.
    app.data = {
        show_access_help: false,
        show_notebook_help: false,
        show_instructor_version_help: false,
        show_student_version_help: false,
        instructor_version: null,
        student_version: null,
        access_url: null,
        uploading: false,
        upload_error: null,
    };

    app.regenerate_access_url = function () {
        axios.post(change_access_url).then(function (res) {
            app.vue.access_url = res.data.access_url;
        })
    }

    app.upload_complete = function (file_name, file_type) {
        app.vue.uploading = false;
        app.get_notebook_urls();
    };

    app.upload_file = function (event) {
        // We need the event to find the file.
        let self = this;
        // Reads the file.
        let input = event.target;
        let file = input.files[0];
        if (file) {
            app.vue.uploading = true;
            let file_type = file.type;
            let file_name = file.name;
            let now = luxon.DateTime.local();
            let date_string = now.toLocaleString(luxon.DateTime.DATETIME_SHORT);
            // Reads the file.
            let reader = new FileReader();
            reader.addEventListener("load", function () {
                axios.post(upload_url,
                    {
                        'file_name': file_name,
                        'file_type': file_type,
                        'date_string': date_string,
                        'notebook_content': reader.result}
                ).then(function (res) {
                    app.vue.uploading = false;
                    app.vue.upload_error = res.data.error;
                    if (!res.data.error) {
                        app.vue.instructor_version = res.data.instructor_version;
                        app.vue.student_version = res.data.student_version;
                    }
                })
            });
            reader.readAsText(file);
        }
    };

    app.get_notebook_urls = function () {
        axios.get(notebook_version_url).then(function (res) {
            app.vue.instructor_version = res.data.instructor_version;
            app.vue.student_version = res.data.student_version;
        });
    };

    // This contains all the methods.
    app.methods = {
        regenerate_access_url: app.regenerate_access_url,
        upload_file: app.upload_file,
    };

    // This creates the Vue instance.
    app.vue = new Vue({
        el: "#vue-target",
        data: app.data,
        methods: app.methods
    });


    // And this initializes it.
    app.init = () => {
        axios.get(change_access_url).then(function (res) {
            app.vue.access_url = res.data.access_url;
        });
        app.get_notebook_urls();
    };

    // Call to the initializer.
    app.init();
};

// This takes the (empty) app object, and initializes it,
// putting all the code i
init(app);
