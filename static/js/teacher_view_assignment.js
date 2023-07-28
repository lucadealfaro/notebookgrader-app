// This will be the object that will contain the Vue attributes
// and be used to initialize it.
let app = {};


// Given an empty app object, initializes it filling its attributes,
// creates a Vue instance, and then initializes the Vue instance.
let init = (app) => {

    // This is the Vue data.
    app.data = {
        show_access_help: false,
        access_url: null,
    };

    app.regenerate_access_url = function () {
        axios.post(change_access_url).then(function (res) {
            app.vue.access_url = res.data.access_url;
        })
    }

    // This contains all the methods.
    app.methods = {
        regenerate_access_url: app.regenerate_access_url,
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
        })
    };

    // Call to the initializer.
    app.init();
};

// This takes the (empty) app object, and initializes it,
// putting all the code i
init(app);
