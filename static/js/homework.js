// This will be the object that will contain the Vue attributes
// and be used to initialize it.
let app = {};


// Given an empty app object, initializes it filling its attributes,
// creates a Vue instance, and then initializes the Vue instance.
let init = (app) => {

    // This is the Vue data.
    app.data = {
        // Help.
        show_deadline_help: false,
        show_late_help: false,
        show_grade_limit_help: false,
        show_grades_help: false,
        show_homework_help: false,
        // Dates.
        date_available: null,
        timestamp_available: null,
        submission_deadline: null,
        date_closes: null,
        timestamp_closes: null,
        can_obtain_notebook: false,
        // Etc.
        grades: [],
        drive_url: null,
        obtain_disabled: false,
        is_grading: false,
        grading_error: null,
        grading_outcome: "",
        cell_source: null,
        max_in_24h: null,
        num_ai_feedback: 0,
        most_recent_request: null,
    };

    app.computed = {
        assignment_is_available: function () {
            return Date.now() >= this.timestamp_available && this.can_obtain_notebook;
        },
        assignment_not_yet_open: function () {
            return Date.now() < this.timestamp_available;
        },
        submission_open: function () {
            return Date.now() < this.timestamp_closes;
        },
        available_grades: function () {
            // Computes the number of recent grades.
            let recent_grades = 0;
            for (let g of this.grades) {
                let grade_date = luxon.DateTime.fromISO(g.grade_date, {zone: "UTC"});
                let is_recent = grade_date.plus({days: 1}) > Date.now();
                if (is_recent) {
                    recent_grades++;
                }
            }
            return this.max_in_24h - recent_grades;
        },
        can_ask_for_grade: function () {
            // We check that we have not asked too recently for a grade.
            return this.most_recent_request == null || 
                Date.now() > this.most_recent_request.plus({minutes: 1});
        }
    };

    app.time_zone = luxon.DateTime.local().zoneName;

    app.enumerate = (a) => {
        // This adds an _idx field to each element of the array.
        let k = 0;
        a.map((e) => {e._idx = k++;});
        return a;
    };

    app.convert_grades = (grades) => {
        // This converts the grade dates to local time.
        for (let g of grades) {
            let grade_date = luxon.DateTime.fromISO(g.grade_date, {zone: "UTC"});
            g.grade_date_display = grade_date.setZone(app.time_zone).toLocaleString(luxon.DateTime.DATETIME_MED_WITH_WEEKDAY);
        }
        return app.enumerate(grades);
    };

    // ok
    app.obtain_assignment = function () {
        app.vue.obtain_disabled = true; // To avoid double clicks.
        axios.post(obtain_assignment_url).then(function (res) {
            app.vue.drive_url = res.data.drive_url;
        }).catch(function (err) {
            if (err.response && err.response.status == 403) {
                location.assign(error_url);
            } else {
                location.assign(internal_error_url);
            }
        });
    };

    app.grade_homework = function () {
        app.vue.is_grading = true;
        app.vue.grading_outcome = null;
        app.vue.cell_source = null;
        app.vue.is_error = null;
        app.vue.most_recent_request = Date.now();
        axios.post(grade_homework_url, {}).then(function (res) {
            app.vue.grading_outcome=res.data.outcome;
            app.vue.grading_error=res.data.is_error;
            app.vue.cell_source = res.data.cell_source;
            if (!res.data.is_error) {
                // We have to watch for changes.
                
            } else {
                app.vue.is_grading = false;
            }
        }).catch(function (err) {
            if (err.response && err.response.status == 403) {
                location.assign(error_url);
            } else {
                location.assign(internal_error_url);
            }
        })
    }

    app.check_new_grade = function () {
        let got_grades = false;
        while (!got_grades) {
            setTimeout(() => {
                // First, we compute the last grade date.
                let update_date = null;
                if (app.vue.grades.length > 0) {
                    update_date = app.vue.grades[0].grade_date;
                }
                // Then, request updated grades.
                axios.get(homework_grades_url).then(function (res) {
                    if (res.data.grades.length > 0 && 
                        (update_date == null ||
                         res.data.grades[0].grade_date > update_date)) {
                            // We got the new grades.
                            app.vue.grades = app.convert_grades(res.data.grades);
                            app.vue.is_grading = false;
                            got_grades = true;
                        }
                }).catch(function(err) {
                    if (err.response && err.response.status == 403) {
                        location.assign(error_url);
                    } else {
                        location.assign(internal_error_url);
                    }
                })
            }, 10000);
        }
    };

    // This contains all the methods.
    app.methods = {
        // Complete as you see fit.
        obtain_assignment: app.obtain_assignment,
        grade_homework: app.grade_homework,
    };


    // This creates the Vue instance.
    app.vue = new Vue({
        el: "#vue-target",
        data: app.data,
        computed: app.computed,
        methods: app.methods
    });


    // And this initializes it.
    app.init = () => {
        axios.get(homework_api_url).then(function (res) {
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
            let local_closes = timestamp_closes.setZone(app.time_zone);
            app.vue.timestamp_closes = timestamp_closes;
            app.vue.date_closes = local_closes.toLocaleString(luxon.DateTime.DATETIME_MED_WITH_WEEKDAY);
            // Drive URL.
            app.vue.drive_url = res.data.drive_url;
            app.vue.can_obtain_notebook = res.data.can_obtain_notebook;
            app.vue.max_in_24h = res.data.max_in_24h;
            app.vue.num_ai_feedback = res.data.num_ai_feedback;
        });
        axios.get(homework_grades_url).then(function (res) {
            app.vue.grades = app.convert_grades(res.data.grades);
            app.vue.most_recent_request = luxon.DateTime.fromISO(res.data.most_recent_request, {zone: "UTC"});
            app.vue.has_pending_requests = res.data.has_pending_requests;
            // If there are pending requests, tries to get the new grades.
            if (app.vue.has_pending_requests) {
                app.check_new_grade();
            }
        });
    };

    // Call to the initializer.
    app.init();
};

// This takes the (empty) app object, and initializes it.
init(app);
