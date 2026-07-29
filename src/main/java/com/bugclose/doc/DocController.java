package com.bugclose.doc;

import org.springframework.core.io.FileSystemResource;
import org.springframework.core.io.Resource;
import org.springframework.http.ContentDisposition;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;

/**
 * 文档库 REST API：上传归档、版本管理、下载与删除
 */
@RestController
@RequestMapping("/api/docs")
public class DocController {

    private final DocService docService;

    public DocController(DocService docService) {
        this.docService = docService;
    }

    /** 文档列表：项目/分类/关键字可选过滤 */
    @GetMapping
    public List<Map<String, Object>> list(@RequestParam(required = false) Long projectId,
                                          @RequestParam(required = false) Document.DocCategory category,
                                          @RequestParam(required = false) String keyword) {
        return docService.search(projectId, category, keyword);
    }

    /** 上传新文档（multipart：file + 元信息） */
    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public Map<String, Object> create(@RequestParam("file") MultipartFile file,
                                      @RequestParam String title,
                                      @RequestParam(required = false) Document.DocCategory category,
                                      @RequestParam(required = false) Long projectId,
                                      @RequestParam(required = false) String description,
                                      @RequestParam(required = false) String uploader) {
        return docService.create(file, title, category, projectId, description, uploader);
    }

    /** 上传新版本 */
    @PostMapping("/{id}/versions")
    @ResponseStatus(HttpStatus.CREATED)
    public Map<String, Object> addVersion(@PathVariable Long id,
                                          @RequestParam("file") MultipartFile file,
                                          @RequestParam(required = false) String remark,
                                          @RequestParam(required = false) String uploader) {
        return docService.addVersion(id, file, remark, uploader);
    }

    /** 版本历史 */
    @GetMapping("/{id}/versions")
    public List<DocumentVersion> listVersions(@PathVariable Long id) {
        return docService.listVersions(id);
    }

    /** 下载指定版本：还原原始文件名（含中文） */
    @GetMapping("/{id}/versions/{versionId}/download")
    public ResponseEntity<Resource> download(@PathVariable Long id, @PathVariable Long versionId) {
        DocService.DownloadFile file = docService.resolveDownload(id, versionId);
        ContentDisposition disposition = ContentDisposition.attachment()
                .filename(file.originalFilename(), StandardCharsets.UTF_8)
                .build();
        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_DISPOSITION, disposition.toString())
                .contentLength(file.fileSize())
                .contentType(MediaType.APPLICATION_OCTET_STREAM)
                .body(new FileSystemResource(file.path()));
    }

    /** 编辑元信息 */
    @PutMapping("/{id}")
    public Map<String, Object> update(@PathVariable Long id, @RequestBody UpdateRequest req) {
        return docService.update(id, req.title(), req.category(), req.projectId(), req.description());
    }

    /** 删除文档及全部版本 */
    @DeleteMapping("/{id}")
    public ResponseEntity<Void> delete(@PathVariable Long id) {
        docService.delete(id);
        return ResponseEntity.noContent().build();
    }

    public record UpdateRequest(String title, Document.DocCategory category, Long projectId, String description) {
    }

    @ExceptionHandler(DocService.DocumentNotFoundException.class)
    public ResponseEntity<Map<String, String>> handleNotFound(DocService.DocumentNotFoundException e) {
        return ResponseEntity.status(HttpStatus.NOT_FOUND).body(Map.of("error", e.getMessage()));
    }

    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<Map<String, String>> handleBadRequest(IllegalArgumentException e) {
        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(Map.of("error", e.getMessage()));
    }

    @ExceptionHandler(UncheckedIOException.class)
    public ResponseEntity<Map<String, String>> handleIoError(UncheckedIOException e) {
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(Map.of("error", e.getMessage()));
    }
}
