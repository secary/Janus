package com.janus.api.controller;

import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;

@Controller
public class PageController {

    @GetMapping("/history")
    public String history() {
        return "forward:/history.html";
    }

    @GetMapping("/admin")
    public String admin() {
        return "forward:/admin.html";
    }
}
