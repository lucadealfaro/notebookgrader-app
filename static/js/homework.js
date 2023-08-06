// This will be the object that will contain the Vue attributes
// and be used to initialize it.
let app = {};


// Given an empty app object, initializes it filling its attributes,
// creates a Vue instance, and then initializes the Vue instance.
let init = (app) => {

    // This is the Vue data.
    app.data = {
        // Help.
        show_homework_help: false,
        show_late_help: false,
        show_grades_help: false,
        // Dates.
        date_available: null,
        timestamp_available: null,
        submission_deadline: null,
        date_closes: null,
        timestamp_closes: null,
        // Etc.
        drive_url: null,
        obtain_disabled: false,
    };

    app.time_zone = luxon.DateTime.local().zoneName;

    app.enumerate = (a) => {
        // This adds an _idx field to each element of the array.
        let k = 0;
        a.map((e) => {e._idx = k++;});
        return a;
    };

    app.obtain_assignment = function () {
        app.vue.obtain_disabled = true; // To avoid double clicks.
        axios.post(obtain_assignment_url).then(function (res) {
            app.vue.drive_url = res.data.drive_url;
        });
    };

    // This contains all the methods.
    app.methods = {
        // Complete as you see fit.
        obtain_assignment: app.obtain_assignment,
    };

    // This creates the Vue instance.
    app.vue = new Vue({
        el: "#vue-target",
        data: app.data,
        methods: app.methods
    });

    // And this initializes it.
    app.init = () => {
        axios.get(homework_details_url).then(function (res) {
            // Availability date.
            let timestamp_available = luxon.DateTime.fromISO(res.data.available_from, {zone: "UTC"});
            let local_available = timestamp_available.setZone(app.time_zone);
            app.vue.date_available = local_available.toLocaleString(luxon.DateTime.DATETIME_MED_WITH_WEEKDAY);
            app.vue.timestamp_available = timestamp_available;
            // Submission deadline.
            let timestamp_deadline = luxon.DateTime.fromISO(res.data.submission_deadline, {zone: "UTC"});
            let local_deadline = timestamp_deadline.setZone(app.time_zone);
            app.vue.submission_deadline = local_deadline.toLocaleString(luxon.DateTime.DATETIME_MED_WITH_WEEKDAY);
            // Closure date.
            let timestamp_closes = luxon.DateTime.fromISO(res.data.available_until, {zone: "UTC"});
            let local_closes = timestamp_close.setZone(app.time_zone);
            app.vue.timestamp_closes = timestamp_closes;
            app.vue.date_closes = local_closes.toLocaleString(luxon.DateTime.DATETIME_MED_WITH_WEEKDAY);
            // Drive URL.
            app.vue.drive_url = res.data.drive_url;
        });
    };

    // Call to the initializer.
    app.init();
};

// This takes the (empty) app object, and initializes it,
// putting all the code i
init(app);