package com.bugclose.upload;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/**
 * Bug 图片上传接口：保存到本地 uploads 目录，返回可访问的 URL
 */
@RestController
@RequestMapping("/api/uploads")
public class UploadController {

    private static final Path UPLOAD_DIR = Paths.get("uploads");
    private static final long MAX_SIZE = 5 * 1024 * 1024; // 单张最大 5MB
    private static final Set<String> ALLOWED_EXT = Set.of("png", "jpg", "jpeg", "gif", "webp", "bmp");

    @PostMapping
    public Map<String, String> upload(@RequestParam("file") MultipartFile file) throws IOException {
        if (file.isEmpty()) {
            throw new IllegalArgumentException("文件为空");
        }
        if (file.getSize() > MAX_SIZE) {
            throw new IllegalArgumentException("图片不能超过 5MB");
        }
        String ext = extensionOf(file.getOriginalFilename());
        if (!ALLOWED_EXT.contains(ext)) {
            throw new IllegalArgumentException("仅支持图片格式: " + ALLOWED_EXT);
        }
        Files.createDirectories(UPLOAD_DIR);
        String filename = UUID.randomUUID() + "." + ext;
        file.transferTo(UPLOAD_DIR.resolve(filename).toAbsolutePath());
        return Map.of("url", "/uploads/" + filename);
    }

    private String extensionOf(String name) {
        if (name == null) return "";
        int dot = name.lastIndexOf('.');
        return dot < 0 ? "" : name.substring(dot + 1).toLowerCase();
    }

    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<Map<String, String>> handleBadRequest(IllegalArgumentException e) {
        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(Map.of("error", e.getMessage()));
    }
}
