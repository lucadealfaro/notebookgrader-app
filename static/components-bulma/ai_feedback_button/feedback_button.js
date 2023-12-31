(function () {
    var feedback_button = {
        props: ['url'],
        data: null,
        methods: {}
    };

    feedback_button.data = function () {
        var data = {
            state: 'ask',
            callback_url: this.url,
            my_num_ai_feedback: app.vue.num_ai_feedback,
        };
        return data;
    };

    feedback_button.methods.ask = function () {
        let self = this;
        self.state = 'confirm';
    };

    feedback_button.methods.confirm = function () {
        let self = this;
        self.state = 'ask';
    };

    Q.register_vue_component('ai_feedback_button', 'components-bulma/ai_feedback_button/feedback_button.html',
        function(template) {
            feedback_button.template = template.data;
            return feedback_button;
        });

})();
