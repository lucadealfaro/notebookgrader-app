// This will be the object that will contain the Vue attributes
// and be used to initialize it.
let app = {};


// Given an empty app object, initializes it filling its attributes,
// creates a Vue instance, and then initializes the Vue instance.
let init = (app) => {

    // This is the Vue data.
    app.data = {
        // Complete as you see fit.
        show_participants_help: false,
    };

    app.enumerate = (a) => {
        // This adds an _idx field to each element of the array.
        let k = 0;
        a.map((e) => {e._idx = k++;});
        return a;
    };

    app.download = function () {
        axios.get(download_url).then(function (res) {
            let blob = new Blob([res.data.csvfile],
                {type: "text/csv"});
            let data_url = URL.createObjectURL(blob);
            let a = document.createElement('a');
            a.href = data_url;
            a.download = res.data.filename;
            // and let's click on it, to do the download!
            a.click();
            // we clean up our act.
            a.remove();
            URL.revokeObjectURL(data_url);
        })
    };

    // This contains all the methods.
    app.methods = {
        download: app.download,
    };

    // This creates the Vue instance.
    app.vue = new Vue({
        el: "#vue-target",
        data: app.data,
        methods: app.methods
    });

    // And this initializes it.
    app.init = () => {
        // Put here any initialization code.
        // Typically this is a server GET call to load the data.
    };

    // Call to the initializer.
    app.init();
};

// This takes the (empty) app object, and initializes it,
// putting all the code i
init(app);
