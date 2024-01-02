(function () {
    var ai_feedback_button = {
        props: ['url'],
        data: null,
        methods: {}
    };

    ai_feedback_button.data = function () {
        var data = {
            state: 'ask',
            callback_url: this.url,
            feedback_url: null,
            error_message: null,
        };
        ai_feedback_button.methods.load.call(data);
        return data;
    };

    ai_feedback_button.methods.ask = function () {
        let self = this;
        self.state = 'confirm';
    };

    ai_feedback_button.methods.cancel = function () {
        let self = this;
        self.state = 'ask';
    }

    ai_feedback_button.methods.confirm = function () {
        let self = this;
        self.state = 'requested';
        axios.post(self.callback_url)
        .then(function (res) {
            self.state = res.data.state;
            self.feedback_url = res.data.feedback_url;
            if (self.state == 'requested') {
                setTimeout(() => {
                    ai_feedback_button.methods.load.call(self);
                }, 10000);
            } else if (state == 'error') {
                self.error_message = res.data.message;
            }
        })
        .catch(function (err) {
            self.state = 'error';
            self.error_message = "An error occurred.";
        });
    };

    ai_feedback_button.methods.load = function () {
        // In use, self will correspond to the data of the button.
        let self = this;
        axios.get(self.callback_url)
            .then(function (res) {
                self.state = res.data.state;
                self.feedback_url = res.data.feedback_url;
                // If we are in the requested state, we have to check if the
                // feedback has been given.
                if (self.state == 'requested') {
                    setTimeout(() => {
                        ai_feedback_button.methods.load.call(self);
                    }, 10000);
                }
            });
    };

    Q.register_vue_component('ai_feedback_button', 'components-bulma/ai_feedback_button/ai_feedback_button.html',
        function(template) {
            ai_feedback_button.template = template.data;
            return ai_feedback_button;
        });

})();
