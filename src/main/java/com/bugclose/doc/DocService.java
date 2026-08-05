package com.bugclose.doc;

import com.bugclose.auth.AccessScope;
import com.bugclose.project.ProjectRepository;
import jakarta.persistence.criteria.Predicate;
import org.springframework.data.domain.Sort;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/**
 * 文档库业务逻辑：上传归档、版本管理、筛选搜索、下载与删除
 */
@Service
@Transactional
public class DocService {

    /** 文档物理文件目录（与 uploads 平级） */
    private static final Path DOC_DIR = Paths.get("docs");
    private static final long MAX_SIZE = 50 * 1024 * 1024; // 单文件最大 50MB
    private static final Set<String> ALLOWED_EXT = Set.of(
            "doc", "docx", "xls", "xlsx", "ppt", "pptx", "pdf",
            "txt", "md", "zip", "rar", "7z", "png", "jpg");

    private final DocumentRepository documentRepository;
    private final DocumentVersionRepository versionRepository;
    private final ProjectRepository projectRepository;
    private final AccessScope accessScope;

    public DocService(DocumentRepository documentRepository,
                      DocumentVersionRepository versionRepository,
                      ProjectRepository projectRepository,
                      AccessScope accessScope) {
        this.documentRepository = documentRepository;
        this.versionRepository = versionRepository;
        this.projectRepository = projectRepository;
        this.accessScope = accessScope;
    }

    /** 条件查询：项目/分类可选，关键字模糊匹配名称和说明，返回含项目名与最新版本信息的视图 */
    @Transactional(readOnly = true)
    public List<Map<String, Object>> search(Long projectId, Document.DocCategory category, String keyword) {
        Specification<Document> spec = (root, query, cb) -> {
            List<Predicate> predicates = new ArrayList<>();
            if (!accessScope.isAllAccess()) {
                predicates.add(root.get("projectId").in(accessScope.visibleProjectIds()));
            }
            if (projectId != null) {
                predicates.add(cb.equal(root.get("projectId"), projectId));
            }
            if (category != null) {
                predicates.add(cb.equal(root.get("category"), category));
            }
            if (keyword != null && !keyword.isBlank()) {
                String like = "%" + keyword.trim().toLowerCase() + "%";
                predicates.add(cb.or(
                        cb.like(cb.lower(root.get("title")), like),
                        cb.like(cb.lower(root.get("description")), like)));
            }
            return cb.and(predicates.toArray(new Predicate[0]));
        };
        List<Document> docs = documentRepository.findAll(spec, Sort.by(Sort.Direction.DESC, "updatedAt"));
        return docs.stream().map(this::toView).toList();
    }

    /** 上传新文档：创建 Document 及 v1 版本 */
    public Map<String, Object> create(MultipartFile file, String title, Document.DocCategory category,
                                      Long projectId, String description, String uploader) {
        if (title == null || title.isBlank()) {
            throw new IllegalArgumentException("文档名称不能为空");
        }
        accessScope.requireProjectOnWrite(projectId);
        validateFile(file);
        LocalDateTime now = LocalDateTime.now();

        Document doc = new Document();
        doc.setProjectId(projectId);
        doc.setTitle(title.trim());
        doc.setCategory(category == null ? Document.DocCategory.OTHER : category);
        doc.setDescription(description == null ? null : description.trim());
        doc.setUploader(uploader == null ? null : uploader.trim());
        doc.setLatestVersionNo(1);
        doc.setCreatedAt(now);
        doc.setUpdatedAt(now);
        doc = documentRepository.save(doc);

        saveVersion(doc, file, 1, "首次上传", uploader);
        return toView(doc);
    }

    /** 上传新版本：版本号自增并刷新文档更新时间 */
    public Map<String, Object> addVersion(Long docId, MultipartFile file, String remark, String uploader) {
        Document doc = findById(docId);
        validateFile(file);
        int nextNo = doc.getLatestVersionNo() + 1;
        saveVersion(doc, file, nextNo, remark, uploader);
        doc.setLatestVersionNo(nextNo);
        doc.setUpdatedAt(LocalDateTime.now());
        documentRepository.save(doc);
        return toView(doc);
    }

    /** 版本历史：最新在前 */
    @Transactional(readOnly = true)
    public List<DocumentVersion> listVersions(Long docId) {
        findById(docId); // 校验文档存在
        return versionRepository.findByDocumentIdOrderByVersionNoDesc(docId);
    }

    /** 定位待下载版本，并返回物理文件路径 */
    @Transactional(readOnly = true)
    public DownloadFile resolveDownload(Long docId, Long versionId) {
        DocumentVersion version = versionRepository.findByIdAndDocumentId(versionId, docId)
                .orElseThrow(() -> new DocumentNotFoundException("版本不存在: id=" + versionId));
        // 校验文档所属项目对当前用户可见
        Long projectId = documentRepository.findById(docId)
                .map(Document::getProjectId).orElse(null);
        accessScope.requireVisible(projectId);
        Path path = DOC_DIR.resolve(version.getStoredName());
        if (!Files.exists(path)) {
            throw new DocumentNotFoundException("文件已丢失: " + version.getOriginalFilename());
        }
        return new DownloadFile(path, version.getOriginalFilename(), version.getFileSize());
    }

    /** 编辑元信息（不涉及文件） */
    public Map<String, Object> update(Long id, String title, Document.DocCategory category,
                                      Long projectId, String description) {
        Document doc = findById(id);
        if (title == null || title.isBlank()) {
            throw new IllegalArgumentException("文档名称不能为空");
        }
        accessScope.requireProjectOnWrite(projectId);
        doc.setTitle(title.trim());
        if (category != null) {
            doc.setCategory(category);
        }
        doc.setProjectId(projectId);
        doc.setDescription(description == null ? null : description.trim());
        doc.setUpdatedAt(LocalDateTime.now());
        return toView(documentRepository.save(doc));
    }

    /** 删除文档：连同全部版本记录与物理文件 */
    public void delete(Long id) {
        Document doc = findById(id);
        List<DocumentVersion> versions = versionRepository.findByDocumentIdOrderByVersionNoDesc(id);
        versionRepository.deleteByDocumentId(id);
        documentRepository.delete(doc);
        // 数据删除成功后再清理物理文件，清理失败不影响业务
        for (DocumentVersion v : versions) {
            try {
                Files.deleteIfExists(DOC_DIR.resolve(v.getStoredName()));
            } catch (IOException ignored) {
                // 文件占用等场景下跳过，不阻塞删除
            }
        }
    }

    private Document findById(Long id) {
        Document doc = documentRepository.findById(id)
                .orElseThrow(() -> new DocumentNotFoundException("文档不存在: id=" + id));
        accessScope.requireVisible(doc.getProjectId());
        return doc;
    }

    /** 校验上传文件：非空、大小、扩展名白名单 */
    private void validateFile(MultipartFile file) {
        if (file == null || file.isEmpty()) {
            throw new IllegalArgumentException("文件为空");
        }
        if (file.getSize() > MAX_SIZE) {
            throw new IllegalArgumentException("文件不能超过 50MB");
        }
        String ext = extensionOf(file.getOriginalFilename());
        if (!ALLOWED_EXT.contains(ext)) {
            throw new IllegalArgumentException("不支持的文件格式，仅支持: " + ALLOWED_EXT);
        }
    }

    /** 落盘并保存版本记录 */
    private void saveVersion(Document doc, MultipartFile file, int versionNo, String remark, String uploader) {
        String ext = extensionOf(file.getOriginalFilename());
        String storedName = UUID.randomUUID() + "." + ext;
        try {
            Files.createDirectories(DOC_DIR);
            file.transferTo(DOC_DIR.resolve(storedName).toAbsolutePath());
        } catch (IOException e) {
            throw new UncheckedIOException("保存文件失败", e);
        }
        DocumentVersion version = new DocumentVersion();
        version.setDocumentId(doc.getId());
        version.setVersionNo(versionNo);
        version.setStoredName(storedName);
        version.setOriginalFilename(file.getOriginalFilename());
        version.setFileSize(file.getSize());
        version.setExt(ext);
        version.setRemark(remark == null ? null : remark.trim());
        version.setUploader(uploader == null ? null : uploader.trim());
        version.setCreatedAt(LocalDateTime.now());
        versionRepository.save(version);
    }

    /** 列表视图：附加项目名称与最新版本文件信息 */
    private Map<String, Object> toView(Document doc) {
        DocumentVersion latest = versionRepository
                .findByDocumentIdOrderByVersionNoDesc(doc.getId())
                .stream().findFirst().orElse(null);
        Map<String, Object> view = new LinkedHashMap<>();
        view.put("id", doc.getId());
        view.put("projectId", doc.getProjectId());
        view.put("projectName", doc.getProjectId() == null ? null
                : projectRepository.findById(doc.getProjectId()).map(p -> p.getName()).orElse(null));
        view.put("title", doc.getTitle());
        view.put("category", doc.getCategory());
        view.put("description", doc.getDescription());
        view.put("latestVersionNo", doc.getLatestVersionNo());
        view.put("uploader", doc.getUploader());
        view.put("createdAt", doc.getCreatedAt());
        view.put("updatedAt", doc.getUpdatedAt());
        if (latest != null) {
            view.put("latestVersionId", latest.getId());
            view.put("latestFilename", latest.getOriginalFilename());
            view.put("latestFileSize", latest.getFileSize());
            view.put("latestUploader", latest.getUploader());
        }
        return view;
    }

    private String extensionOf(String name) {
        if (name == null) return "";
        int dot = name.lastIndexOf('.');
        return dot < 0 ? "" : name.substring(dot + 1).toLowerCase();
    }

    /** 下载文件描述 */
    public record DownloadFile(Path path, String originalFilename, long fileSize) {
    }

    /** 文档或版本不存在异常 */
    public static class DocumentNotFoundException extends RuntimeException {
        public DocumentNotFoundException(String message) {
            super(message);
        }
    }
}
