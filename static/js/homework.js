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
        max_points: 0,
        drive_url: null,
        obtain_disabled: false,
        is_grading: false,
        grading_error: null,
        grading_outcome: "",
        cell_source: null,
        max_in_24h: null,
        max_ai_feedback: 0,
        most_recent_request: null,
        star_indices: [1, 2, 3, 4, 5],
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
        num_received_ai_feedback: function () {
            let n = 0;
            for (let g of this.grades) {
                if (g.ai_state == 'received' || g.ai_state == 'requested') {
                    n++;
                }
            }
            return n;
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
            app.convert_time(g);
            app.set_ai_info(g);
        }
        return app.enumerate(grades);
    };

    app.convert_time = (g) => {
        let grade_date = luxon.DateTime.fromISO(g.grade_date, {zone: "UTC"});
        g.grade_date_display = grade_date.setZone(app.time_zone).toLocaleString(luxon.DateTime.DATETIME_MED_WITH_WEEKDAY);
    }

    app.set_ai_info = (g) => {
        // Initializes the AI feedback info so Vue pays attention to it.
        g.ai_state = 'ask';
        g.ai_feedback_url = null;
        g.ai_error_message = null;
        g.num_stars_display = 0;
        g.num_stars_assigned = 0;
    };

    app.get_ai_state = (g, delay=10000) => {
        // Checks the AI feedback for the grade.
        axios.get(g.ai_url).then(function (res) {
            g.ai_state = res.data.state;
            g.ai_feedback_url = res.data.feedback_url;
            g.ai_error_message = res.data.message;
            // If we are in the requested state, we have to check if the feedback has been given.
            if (g.ai_state == 'requested') {
                setTimeout(() => {
                    app.get_ai_state(g, Math.min(delay * 1.2, 5 * 60 * 1000));
                }, delay);
            }
            // If we are in the received state, we have to get the number of stars.
            if (g.ai_state == 'received') {
                app.get_stars(g);
            }
        }).catch(function (err) {
            if (err.response && err.response.status == 403) {
                location.assign(error_url);
            } else {
                location.assign(internal_error_url);
            }
        })
    };

    app.ai_ask = function (g_idx) {
        let g = app.vue.grades[g_idx];
        g.ai_state = 'confirm';
    };

    app.ai_cancel = function (g_idx) {
        let g = app.vue.grades[g_idx];
        g.ai_state = 'ask';
    };

    app.ai_confirm = function (g_idx) {
        let g = app.vue.grades[g_idx];
        g.ai_state = 'requested';
        axios.post(g.ai_url).then(function (res) {
            g.ai_state = res.data.state;
            g.ai_feedback_url = res.data.feedback_url;
            g.ai_error_message = res.data.message;
            if (g.ai_state == 'requested') {
                setTimeout(() => {
                    app.get_ai_state(g);
                }, 10000);
            }
            // If we are in the received state, we have to get the number of stars.
            if (g.ai_state == 'received') {
                app.get_stars(g);
            }            
        }).catch(function (err) {
            if (err.response && err.response.status == 403) {
                location.assign(error_url);
            } else {
                location.assign(internal_error_url);
            }
        });
    }

    // ok
    app.obtain_assignment = function () {
        if (app.computed.assignment_is_available.call(app.vue) &&
             !app.vue.obtain_disabled) {
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
        }
    };

    app.grade_homework = function () {
        app.vue.is_grading = true;
        app.vue.grading_outcome = null;
        app.vue.cell_source = null;
        app.vue.is_error = null;
        app.vue.most_recent_request = Date.now();
        axios.post(grade_homework_url, {}).then(function (res) {
            app.vue.grading_outcome = res.data.outcome;
            app.vue.grading_error = res.data.is_error;
            app.vue.cell_source = res.data.cell_source;
            if (!res.data.is_error) {
                // We have to watch for changes.
                app.check_new_grade();
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

    app.check_new_grade = function (delay=10000) {
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
                        // Makes a dictionary of id to old grade, to save the AI state.
                        let old_grades = {};
                        for (let g of app.vue.grades) {
                            old_grades[g.id] = g;
                        }
                        // Updates the grades.
                        new_grades = [];
                        for (let g of res.data.grades) {
                            if (g.id in old_grades) {
                                // We already had this grade.
                                old_g = old_grades[g.id];
                                old_g.is_valid = g.is_valid;
                                new_grades.push(old_g);
                            } else {
                                // This is a new grade.
                                app.convert_time(g);
                                app.set_ai_info(g);
                                app.get_ai_state(g);
                                new_grades.push(g);
                            }
                        }
                        new_grades = app.enumerate(new_grades);
                        app.vue.grades = new_grades;
                        app.vue.is_grading = false;
                        app.vue.grading_outcome = "";
                        app.vue.grading_error = "";
                        app.vue.cell_source = "";
                    } else {
                        // We have to wait a bit more.
                        app.check_new_grade(Math.min(delay * 1.2, 5 * 60 * 1000));
                    }
            }).catch(function(err) {
                if (err.response && err.response.status == 403) {
                    location.assign(error_url);
                } else {
                    location.assign(internal_error_url);
                }
            })
        }, delay);
    };

    // Star methods. 
    app.stars_over = function (g_idx, star_idx) {
        let g = app.vue.grades[g_idx];
        g.num_stars_display = star_idx;
    };

    app.stars_out = function (g_idx) {
        let g = app.vue.grades[g_idx];
        g.num_stars_display = g.num_stars_assigned;
    };

    app.set_stars = function (g_idx, star_idx) {
        let g = app.vue.grades[g_idx];
        g.num_stars_assigned = star_idx;
        axios.post(g.ai_rate_url, {num_stars: g.num_stars_assigned});
    };

    app.get_stars = function (g) {
        axios.get(g.ai_rate_url).then(function (res) {
            g.num_stars_assigned = res.data.num_stars;
            g.num_stars_display = res.data.num_stars;
        })
    };

    // This contains all the methods.
    app.methods = {
        // Complete as you see fit.
        obtain_assignment: app.obtain_assignment,
        grade_homework: app.grade_homework,
        ai_ask: app.ai_ask,
        ai_cancel: app.ai_cancel,
        ai_confirm: app.ai_confirm,
        stars_over: app.stars_over,
        stars_out: app.stars_out,
        set_stars: app.set_stars,
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
            app.vue.max_ai_feedback = res.data.num_ai_feedback;
            app.vue.max_points = res.data.max_points;
        }).catch(function (err) {
            if (err.response && err.response.status == 403) {
                location.assign(error_url);
            } else {
                location.assign(internal_error_url);
            }
        });
        axios.get(homework_grades_url).then(function (res) {
            app.vue.grades = app.convert_grades(res.data.grades);
            // Checks the AI feedback for each grade.
            for (let g of app.vue.grades) {
                app.get_ai_state(g);
            }
            app.vue.most_recent_request = luxon.DateTime.fromISO(res.data.most_recent_request, {zone: "UTC"});
            app.vue.has_pending_requests = res.data.has_pending_requests;
            // If there are pending requests, tries to get the new grades.
            if (app.vue.has_pending_requests) {
                app.check_new_grade();
            }
        }).catch(function (err) {
            if (err.response && err.response.status == 403) {
                location.assign(error_url);
            } else {
                location.assign(internal_error_url);
            }
        });
    };

    // Call to the initializer.
    app.init();
};

// This takes the (empty) app object, and initializes it.
init(app);
